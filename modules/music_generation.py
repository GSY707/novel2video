# modules/music_generation.py

from typing import List, Dict
from .llm import  _call_llm_with_retry, _load_prompt_vars
from file_of_film_project import save_music_prompt, get_chapter_list, get_chapter_summary, get_list_shots, read_shot_info
# 已实现函数（只调用，不修改）
# 文件管理 & 音乐系统
# save_music_prompt(...)
# get_all_music_ids(...)

# LLM 相关
# _load_prompt_vars(filename)
# _call_llm_with_retry(prompt_vars, context_data, output_format="yaml", model_name="DeepSeek")


# modules/music_generation.py


# ====== 已实现函数（只调用，不修改） ======
# Shot System
# get_list_shots(project_name)
# read_shot_info(project_name, shot_id)

# Text System
# get_chapter_list(project_name)
# get_chapter_summary(project_name, chapter_id)

# Music System
# save_music_prompt(project_name, music_info)

# LLM
# _load_prompt_vars(filename)
# _call_llm_with_retry(prompt_vars, context_data, output_format="yaml", model_name="DeepSeek")


# ====== 工具函数 ======

def _to_minutes(timestamp: str) -> float:
    parts = timestamp.split(":")
    parts = [int(p) for p in parts]

    if len(parts) == 3:
        h, m, s = parts
        return h * 60 + m + s / 60.0
    elif len(parts) == 2:
        m, s = parts
        return m + s / 60.0
    return 0.0


def _normalize_time(time_str: str, base_time: float) -> float:
    try:
        m, s = time_str.split(":")
        return base_time + int(m) + int(s) / 60.0
    except Exception:
        return base_time


def _shots_to_text(shots: List[Dict]) -> str:
    lines = []
    for i, s in enumerate(shots, 1):
        lines.append(
            f"{i}. timestamp: {s.get('时长','')}, "
            f"shot_type: {s.get('镜头类型','')}, "
            f"demand: {s.get('镜头表达需求','')}, "
            f"object_info: {s.get('主要对象','')}"
        )
    return "\n".join(lines)


def _build_chapter_context(project_name: str) -> str:
    """
    将所有章节总结拼接为背景上下文
    """
    chapter_ids = get_chapter_list(project_name)
    summaries = []

    for cid in chapter_ids:
        summary = get_chapter_summary(project_name, cid)
        if summary:
            summaries.append(f"Chapter {cid}: {summary}")

    return "\n".join(summaries)


# ====== 核心函数 ======

def _generate_music_prompts(project_name: str):
    """
    主音乐生成逻辑（不依赖外部传参）
    """

    WINDOW_SIZE = 30
    STEP_SIZE = 25
    BATCH_SIZE = 20

    # ====== 1. 读取所有镜头并计算总时长 ======
    shot_ids = get_list_shots(project_name)
    all_shots = []

    total_duration_minutes = 0.0

    for sid in shot_ids:
        info = read_shot_info(project_name, sid)
        if not info:
            continue

        ts = info.get("时长", "0:03")
        minute = _to_minutes(ts)

        total_duration_minutes = max(total_duration_minutes, minute)

        info["shot_id"] = sid
        all_shots.append(info)

    if not all_shots:
        return

    # ====== 2. 章节上下文 ======
    chapter_context = _build_chapter_context(project_name)

    # ====== 3. Prompt 预加载 ======
    analyzer_prompt = _load_prompt_vars("Music_Batch_Analyzer.yaml")
    director_prompt = _load_prompt_vars("Music_Director.yaml")

    current_time = 0.0
    music_history = []

    # ====== 4. 时间滑窗处理 ======
    while current_time < total_duration_minutes:
        window_end = min(current_time + WINDOW_SIZE, total_duration_minutes)

        window_shots = [
            s for s in all_shots
            if current_time <= _to_minutes(s.get("timestamp", "0:03")) < window_end
        ]

        if not window_shots:
            current_time += STEP_SIZE
            continue

        # ---- 重叠区判断 ----
        overlap_msg = "No music playing at start."
        overlap_end = current_time + (WINDOW_SIZE - STEP_SIZE)

        for m in music_history:
            if current_time <= m["start"] < overlap_end:
                overlap_msg = (
                    f"Music already playing since {m['start']}m. "
                    f"Prompt: {m['prompt']}"
                )
                break

        # ---- Batch Analyzer ----
        summaries = []

        for i in range(0, len(window_shots), BATCH_SIZE):
            batch = window_shots[i:i + BATCH_SIZE]
            text = _shots_to_text(batch)

            summary = _call_llm_with_retry(
                analyzer_prompt,
                {"shots_text": text},
                output_format="text"
            )

            if summary:
                summaries.append(summary.strip())

        if not summaries:
            current_time += STEP_SIZE
            continue

        timeline_summary = "\n".join(summaries)

        # ---- Music Director ----
        response = _call_llm_with_retry(
            director_prompt,
            {
                "overlap_context": overlap_msg,
                "timeline_summary": timeline_summary,
                "chapter_context": chapter_context
            },
            output_format="json"
        )

        if isinstance(response, dict):
            abs_time = _normalize_time(
                response.get("selected_start_time"),
                current_time
            )

            save_music_prompt(
                project_name,
                {
                    "start_time": abs_time,
                    "prompt": response.get("music_prompt", ""),
                    "reason": response.get("reason", "")
                }
            )

            music_history.append({
                "start": abs_time,
                "prompt": response.get("music_prompt", "")
            })

        current_time += STEP_SIZE

