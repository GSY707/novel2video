import os
import io
import torch
import gc
from PIL import Image
from diffusers import (
    DiffusionPipeline, 
    StableDiffusionXLPipeline,
    EulerAncestralDiscreteScheduler,
    EulerDiscreteScheduler,
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
        
        # 添加性能优化标志
        self.is_optimized = False

    def _optimize_pipeline(self, model_name, load_type):
        """对已加载的管道进行性能优化"""
        if self.pipe is None:
            return
            
        # 只对SDXL模型和CUDA设备进行优化
        if self.device != "cuda":
            print(f"设备 {self.device} 不支持CUDA优化，跳过优化")
            return
            
        print(f"对 {model_name} 应用性能优化...")
        
        try:
            # 根据模型类型应用不同优化
            if load_type in ["sdxl_folder", "sdxl_single_file"] and model_name != "NoobAI-XL":
                # SDXL模型优化
                # 启用VAE优化（减少显存使用）
                try:
                    self.pipe.enable_vae_slicing()
                    self.pipe.enable_vae_tiling()
                    print("已启用VAE切片和平铺优化")
                except:
                    print("VAE优化不可用，跳过")
                
                # 启用注意力切片（如果显存不足）
                try:
                    self.pipe.enable_attention_slicing(slice_size=1)
                    print("已启用注意力切片")
                except:
                    print("注意力切片不可用，跳过")
                
                # 尝试启用xformers或sdpa优化
                try:
                    # 先尝试启用xformers
                    self.pipe.enable_xformers_memory_efficient_attention()
                    print("已启用xformers内存高效注意力")
                except:
                    try:
                        # 如果xformers不可用，尝试使用PyTorch 2.0的scaled_dot_product_attention
                        # 这需要设置attn_implementation，但我们已经加载了模型
                        # 所以尝试启用模型CPU卸载作为替代
                        self.pipe.enable_model_cpu_offload()
                        print("已启用模型CPU卸载优化")
                    except:
                        print("高级优化不可用，使用默认设置")
                
                # 对于非NoobAI模型，使用更快的调度器
                if "NoobAI" not in model_name:
                    try:
                        self.pipe.scheduler = EulerDiscreteScheduler.from_config(
                            self.pipe.scheduler.config,
                            timestep_spacing="trailing"
                        )
                        print("已启用EulerDiscrete快速调度器")
                    except:
                        print("无法更改调度器，使用原有调度器")
                
                # 预热模型（让第一次推理更快）
                print("预热模型...")
                with torch.no_grad():
                    try:
                        # 使用最小分辨率进行预热
                        _ = self.pipe("warmup", num_inference_steps=1, height=64, width=64)
                        print("模型预热完成")
                    except Exception as e:
                        print(f"预热失败: {e}")
            if model_name == "NoobAI-XL":
                # SDXL模型优化
                # 启用VAE优化（减少显存使用）
                
                try:
                    self.pipe.enable_vae_slicing()
                    self.pipe.enable_vae_tiling()
                    print("已启用VAE切片和平铺优化")
                except:
                    print("VAE优化不可用，跳过")
                
                # 启用注意力切片（如果显存不足）
                try:
                    self.pipe.enable_attention_slicing(slice_size=1)
                    print("已启用注意力切片")
                except:
                    print("注意力切片不可用，跳过")
                
                # 尝试启用xformers或sdpa优化
                try:
                    # 先尝试启用xformers
                    self.pipe.enable_xformers_memory_efficient_attention()
                    print("已启用xformers内存高效注意力")
                except:
                    try:
                        # 如果xformers不可用，尝试使用PyTorch 2.0的scaled_dot_product_attention
                        # 这需要设置attn_implementation，但我们已经加载了模型
                        # 所以尝试启用模型CPU卸载作为替代
                        self.pipe.enable_model_cpu_offload()
                        print("已启用模型CPU卸载优化")
                    except:
                        print("高级优化不可用，使用默认设置")
                
                # 预热模型（让第一次推理更快）
                print("预热模型...")
                with torch.no_grad():
                    try:
                        # 使用最小分辨率进行预热
                        _ = self.pipe("warmup", num_inference_steps=1, height=64, width=64)
                        print("模型预热完成")
                    except Exception as e:
                        print(f"预热失败: {e}")

            elif load_type == "Z-Image-Turbo-fp8":
                # Z-Image-Turbo模型已经优化过，只需要确保编译
                try:
                    self.pipe.transformer.compile()
                    print("Z-Image-Turbo模型已编译优化")
                except:
                    print("Z-Image-Turbo模型编译失败，继续使用")
            
            # 清空缓存
            torch.cuda.empty_cache()
            gc.collect()
            
            self.is_optimized = True
            print(f"{model_name} 优化完成")
            
        except Exception as e:
            print(f"优化过程中出现错误: {e}")
            print("将继续使用未优化的管道")

    def _load_model(self, model_name):
        if model_name == self.current_model_name and self.pipe is not None:
            return

        # 卸载当前模型
        if self.pipe is not None:
            del self.pipe
            torch.cuda.empty_cache()
            gc.collect()
            
        conf = config.MODELS.get(model_name)
        if not conf:
            raise ValueError(f"Model {model_name} not found.")

        path = conf["path"]
        load_type = conf["type"]
        
        print(f"Loading {model_name} ({load_type}) from {path}...")
        
        try:
            # 清空GPU缓存
            torch.cuda.empty_cache()
            
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
                # 尝试使用更快的注意力实现
                try:
                    self.pipe = StableDiffusionXLPipeline.from_pretrained(
                        path,
                        torch_dtype=self.dtype,
                        use_safetensors=True,
                        local_files_only=True,
                        attn_implementation="sdpa"  # PyTorch 2.0+ 原生注意力
                    )
                    print("已启用SDPA注意力优化")
                except:
                    # 回退到默认实现
                    self.pipe = StableDiffusionXLPipeline.from_pretrained(
                        path,
                        torch_dtype=self.dtype,
                        use_safetensors=True,
                        local_files_only=True
                    )
                    print("使用默认注意力实现")

            # --- 方式 C: 单文件加载 (NoobAI, MiaoMiao) ---
            elif load_type == "sdxl_single_file":
                # 尝试使用更快的注意力实现
                if "NoobAI" in model_name:
                    print(f"正在以 V-prediction 配置加载 NoobAI 模型...")
                    self.pipe = StableDiffusionXLPipeline.from_single_file(
                        path,
                        torch_dtype=self.dtype,
                        use_safetensors=True,
                        local_files_only=True,
                        # 最关键的两个参数
                        prediction_type="v_prediction", # 告知管道使用V-prediction
                        force_zeros_for_empty_prompt=False, # V-pred模型通常需禁用此选项
                    )
                else:
                    try:
                        self.pipe = StableDiffusionXLPipeline.from_single_file(
                            path,
                            torch_dtype=self.dtype,
                            use_safetensors=True,
                            local_files_only=True,
                            variant="fp16",  # 如果可用
                            attn_implementation="sdpa"  # PyTorch 2.0+ 原生注意力
                        )
                        print("已启用SDPA注意力优化")
                    except:
                        # 回退到默认实现
                        self.pipe = StableDiffusionXLPipeline.from_single_file(
                            path,
                            torch_dtype=self.dtype,
                            use_safetensors=True,
                            local_files_only=True
                        )
                        print("使用默认注意力实现")
                    
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
            # 应用性能优化
            self._optimize_pipeline(model_name, load_type)

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

        # 4. 推理
        try:
            # 同步CUDA设备以确保准确计时
            if self.device == "cuda":
                torch.cuda.synchronize()
                
            with torch.no_grad():
                image = self.pipe(**run_params).images
            
            img_byte_arr = io.BytesIO()
            image[0].save(img_byte_arr, format='PNG')
            
            # 清理缓存
            if self.device == "cuda":
                torch.cuda.empty_cache()
                
            return img_byte_arr.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

_engine = ImageGeneratorEngine()

def generate_image_core(prompt, model_name, width, height):
    return _engine.generate(prompt, model_name, width, height)