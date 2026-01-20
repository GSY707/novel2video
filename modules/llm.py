import json
import yaml
import re
from copy import deepcopy
from .AI_api import llm
import os
import importlib.util
class LLMOutputError(Exception):
    pass


def _call_llm_with_retry(
    prompt_vars: dict,
    context_data,
    output_format: str = "yaml",
    model_name: str = "DeepSeek",
):
    """
    Robust LLM call with:
    - continuation
    - retry
    - restart
    - strict output contract
    """

    # -------------------------
    # Configuration
    # -------------------------
    MAX_CONTINUE = 3
    MAX_RETRY = 2
    MAX_RESTART = 1

    if output_format not in ("yaml", "json", "text"):
        raise ValueError(f"Unsupported output_format: {output_format}")

    # -------------------------
    # Prompt construction
    # -------------------------
    system_prompt = prompt_vars.get("SYSTEM_PROMPT", "").strip()

    user_template = prompt_vars.get("USER_PROMPT_TEMPLATE", "")
    if isinstance(context_data, (dict, list)):
        context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
    else:
        context_str = str(context_data)

    user_prompt = user_template + "\n" + context_str

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # -------------------------
    # Helpers
    # -------------------------
    def _call(messages):
        resp = llm(messages, llm_name=model_name)
        return resp if isinstance(resp, str) else str(resp)

    def _strip_markdown(text: str) -> str:
        text = re.sub(r"```(yaml|json)?", "", text)
        return text.replace("```", "").strip()

    def _parse(text: str):
        if output_format == "text":
            return text

        try:
            if output_format == "json":
                return json.loads(text)
            else:
                return yaml.safe_load(text)
        except Exception as e:
            raise LLMOutputError(str(e))

    def _is_obviously_truncated(text: str) -> bool:
        """
        Heuristic only. Real trust is on parsing failure.
        """
        stripped = text.rstrip()
        if output_format == "json":
            return not stripped.endswith(("}", "]"))
        if output_format == "yaml":
            return False
        return False

    def _continue_prompt(last_chunk: str) -> str:
        tail = last_chunk[-200:]
        return (
            "你的输出被中断了。\n"
            "请从上一次输出的结尾继续，"
            "不要重复已经输出的内容。\n"
            f"上一次输出的结尾是：\n{tail}"
        )

    def _restart_prompt() -> str:
        return (
            "你之前的输出已被系统判定为无效。\n"
            "请忽略之前的所有输出和上下文，\n"
            "从头开始，仅根据当前输入生成完整且合法的最终输出。\n"
            "只输出最终结果，不要解释。"
        )

    # -------------------------
    # Main loop
    # -------------------------
    restart_count = 0

    while restart_count <= MAX_RESTART:
        messages = deepcopy(base_messages)
        retry_count = 0

        while retry_count <= MAX_RETRY:
            full_text = ""
            continue_count = 0

            # --- First call ---
            current = _call(messages)
            full_text += current

            # --- Continue if needed ---
            while continue_count < MAX_CONTINUE:
                try:
                    cleaned = _strip_markdown(full_text)
                    _parse(cleaned)
                    break  # parse success
                except LLMOutputError:
                    if not _is_obviously_truncated(full_text):
                        break

                continue_count += 1
                messages.append({"role": "assistant", "content": current})
                messages.append(
                    {"role": "user", "content": _continue_prompt(current)}
                )
                current = _call(messages)
                full_text += current

            # --- Final parse attempt ---
            try:
                cleaned = _strip_markdown(full_text)
                return _parse(cleaned)
            except LLMOutputError:
                retry_count += 1
                if retry_count > MAX_RETRY:
                    break

                # retry with correction instruction
                messages = deepcopy(base_messages)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "你的上一次输出不符合格式要求。\n"
                            f"请严格按照 {output_format.upper()} 格式重新输出。\n"
                            "不要包含解释、注释或多余内容。"
                        ),
                    }
                )

        # --- Restart ---
        restart_count += 1
        if restart_count > MAX_RESTART:
            break

        messages = deepcopy(base_messages)
        messages.append({"role": "user", "content": _restart_prompt()})

    raise LLMOutputError("LLM failed to produce valid output after retries and restart.")

# ==============================================================================
# Helper Function: 动态加载提示词文件
# ==============================================================================

PROMPT_DIR = "C:/skzy/computer/v3/prompt"

def _load_prompt_vars(prompt_name: str):
    """
    安全加载 YAML 格式提示词。
    输入：prompt_name（不含后缀）
    输出结构保持不变。
    支持运行期热更新。
    """
    file_path = os.path.join(PROMPT_DIR, f"{prompt_name}")

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