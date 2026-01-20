import os
import io
import torch
from PIL import Image
from diffusers import (
    DiffusionPipeline, 
    StableDiffusionXLPipeline,
    EulerAncestralDiscreteScheduler,
    ZImagePipeline
)
from . import config

class ImageGeneratorEngine:
    def __init__(self):
        self.current_model_name = None
        self.pipe = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # 现代显卡用 float16 节省显存，旧卡可能需要 float32
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

    def _load_model(self, model_name):
        if model_name == self.current_model_name and self.pipe is not None:
            return

        # 卸载当前模型
        if self.pipe is not None:
            del self.pipe
            torch.cuda.empty_cache()
            
        conf = config.MODELS.get(model_name)
        if not conf:
            raise ValueError(f"Model {model_name} not found.")

        path = conf["path"]
        load_type = conf["type"]
        
        print(f"Loading {model_name} ({load_type}) from {path}...")
        
        try:
            # --- 方式 A: 文件夹加载 + 自定义代码 (Z-Image, Qwen) ---
            if load_type == "custom_folder":
                self.pipe = DiffusionPipeline.from_pretrained(
                    path,
                    torch_dtype=self.dtype,
                    use_safetensors=True,
                    trust_remote_code=True, # 允许执行文件夹内的 pipeline.py
                    local_files_only=True   # 强制离线
                )
            
            # --- 方式 B: 标准 SDXL 文件夹 (Koala) ---
            elif load_type == "sdxl_folder":
                self.pipe = StableDiffusionXLPipeline.from_pretrained(
                    path,
                    torch_dtype=self.dtype,
                    use_safetensors=True,
                    local_files_only=True
                )

            # --- 方式 C: 单文件加载 (NoobAI, MiaoMiao) ---
            elif load_type == "sdxl_single_file":
                self.pipe = StableDiffusionXLPipeline.from_single_file(
                    path,
                    torch_dtype=self.dtype,
                    use_safetensors=True,
                    local_files_only=True 
                )
            elif load_type == "Z-Image-Turbo-fp8":
                try:
                    pipe = ZImagePipeline.from_pretrained(
                        path,
                        torch_dtype=torch.float8_e4m3fn,
                        low_cpu_mem_usage=False,
                    )
                    pipe.transformer.compile()
                except TypeError as e:
                    # 如果当前diffusers或PyTorch版本不支持直接使用torch.float8
                    print(f"直接使用torch.float8报错: {e}")
                    print("将尝试使用BF16加载，但模型本身是FP8权重，仍有一定显存优势。")
                    pipe = ZImagePipeline.from_pretrained(
                        path,
                        torch_dtype=torch.bfloat16,  # 降级为BF16加载
                        low_cpu_mem_usage=False,
                    )
                    pipe.transformer.compile()
                
            # 特殊配置：NoobAI 需要 Euler Ancestral 调度器
            if "NoobAI" in model_name:
                self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
                    self.pipe.scheduler.config, 
                    use_karras_sigmas=True
                )
            
            self.pipe.to(self.device)
            self.current_model_name = model_name

        except Exception as e:
            raise RuntimeError(f"Failed to load {model_name}: {str(e)}")

    def generate(self, prompt, model_name, width, height, negative_prompt=None):
        self._load_model(model_name)
        
        conf = config.MODELS[model_name]
        defaults = conf.get("default_params", {})
        
        # 1. 准备参数
        # 优先使用函数传入的参数，否则使用 config 默认
        run_params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_inference_steps": defaults.get("num_inference_steps", 25),
            "guidance_scale": defaults.get("guidance_scale", 7.0),
        }
        
        # 2. 处理负面提示词
        # 如果调用者没传，就用 Config 里的默认值
        final_negative = negative_prompt if negative_prompt is not None else config.DEFAULT_NEGATIVE_PROMPT
        run_params["negative_prompt"] = final_negative

        # 3. 推理
        try:
            with torch.no_grad():
                image = self.pipe(**run_params).images
            
            img_byte_arr = io.BytesIO()
            image[0].save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

_engine = ImageGeneratorEngine()

def generate_image_core(prompt, model_name, width, height):
    return _engine.generate(prompt, model_name, width, height)