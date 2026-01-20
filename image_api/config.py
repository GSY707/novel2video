import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_ROOT = "C:/web/project_files/model"

# 全局默认负面提示词
DEFAULT_NEGATIVE_PROMPT = (
    "low quality, bad quality, sketches, bad anatomy, deformed, "
    "disfigured, watermark, text, signature, mutation, ugly"
)
'''
    # --- 2. Qwen Image (通义千问图像) ---
    "Qwen-Image": {
        "path": os.path.join(MODEL_ROOT, "Qwen_Image"),
        "type": "custom_folder",
        "desc": "Qwen 20B 图像生成模型，擅长文字渲染。",
        "speed": "慢 (模型较大)",
        "feature": "业界领先的文字生成能力，支持复杂构图。",
        "hf_repo_id": "Qwen/Qwen-Image", 
        "default_params": {
            "num_inference_steps": 28, 
            "guidance_scale": 5.0
        }
    },
'''
MODELS = {
    # --- 1. Z Image Turbo (阿里通义新模型) ---
    "Z Image Turbo": {
        "path": os.path.join(MODEL_ROOT, "Z_Image_Turbo"),
        "type": "custom_folder",
        "desc": "阿里通义极速模型，8步出图，DiT架构。",
        "speed": "极快 (8步)",
        "feature": "中英双语支持，指令遵循强。",
        #"hf_repo_id": "Tongyi-MAI/Z-Image-Turbo", # 用于下载脚本
        "default_params": {
            "num_inference_steps": 9, 
            "guidance_scale": 0, # Guidance should be 0 for the Turbo models
        }
    },
    # --- 3. KOALA-1B (SDXL 蒸馏版) ---
    "KOALA-1B": {
        "path": os.path.join(MODEL_ROOT, "KOALA_1B"),
        "type": "sdxl_folder", # 这是一个标准 SDXL 结构，但为了包含unet配置，下载文件夹更好
        "desc": "SDXL 的轻量化蒸馏版本，速度快。",
        "speed": "快",
        "feature": "1B 参数量，适合显存较小的设备。",
        "hf_repo_id": "etri-vilab/koala-1b",
        "default_params": {
            "num_inference_steps": 20, 
            "guidance_scale": 4.5
        }
    },

    # --- 4. NoobAI-XL (标准 SDXL 单文件) ---
    "NoobAI-XL": {
        "path": os.path.join(MODEL_ROOT, "checkpoints", "NoobAI-XL.safetensors"),
        "type": "sdxl_single_file",
        "desc": "顶级二次元模型，V-Prediction 版本。",
        "speed": "中等",
        "feature": "二次元画质 SOTA，标签敏感。",
        "hf_file_url": "https://huggingface.co/Laxhar/noobai-XL-Vpred-1.0/resolve/main/noobai-XL-Vpred-1.0.safetensors",
        "default_params": {
            "num_inference_steps": 28, 
            "guidance_scale": 5.5,
            "scheduler_type": "euler_ancestral" # 必须用 Euler A
        }
    },

     # --- 5. MiaoMiao Harem (SD1.5 或 SDXL) ---
    "MiaoMiao Harem": {
        "path": os.path.join(MODEL_ROOT, "checkpoints", "MiaoMiao_Harem.safetensors"),
        "type": "sdxl_single_file", # 假设是 SDXL，如果是 1.5 请改为 sd15_single_file
        "desc": "特定风格微调模型。",
        "speed": "中等",
        "feature": "色彩鲜艳，风格独特。",
        "#note": "此处假设为本地已有文件，若需下载请填 URL",
        "default_params": {
            "num_inference_steps": 30, 
            "guidance_scale": 7.0
        }
    }
}