import os
import yaml

PROMPT_DIR = "C:/skzy/computer/v3/prompt"

def _load_prompt_vars(prompt_name: str):
    """
    安全加载 YAML 格式提示词。
    输入：prompt_name（不含后缀）
    输出结构保持不变。
    支持运行期热更新。
    """
    file_path = os.path.join(PROMPT_DIR, f"{prompt_name}.yaml")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"提示词文件未找到: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    prompts = data.get("prompts", {})

    return {
        "SYSTEM_PROMPT": prompts.get("SYSTEM_PROMPT", ""),
        "USER_PROMPT_TEMPLATE": prompts.get("USER_PROMPT_TEMPLATE", ""),
        "CORRECTION_PROMPT_TEMPLATE": prompts.get("CORRECTION_PROMPT_TEMPLATE", "")
    }
