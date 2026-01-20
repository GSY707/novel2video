from .core import generate_image_core
from .config import MODELS, DEFAULT_NEGATIVE_PROMPT

def generate_image(prompt, model_name="KOALA-1B", width=1024, height=1024):
    """
    生成图片接口
    无需手动处理负面提示词，模块会自动注入默认值。
    """
    if model_name not in MODELS:
        # Fallback 逻辑
        model_name = "Z Image Turbo"
        
    return generate_image_core(prompt, model_name, width, height)

def get_model_list():
    """返回模型信息字典"""
    info = {}
    for name, data in MODELS.items():
        info[name] = (
            f"{data['desc']} "
            f"[速度: {data['speed']}] "
            f"[特性: {data['feature']}]"
        )
    return info

def get_lora_list(model_name):
    # 此处逻辑保持不变，扫描文件夹即可
    return {}