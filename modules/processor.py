import os
import re
import json
import yaml
import importlib.util
import datetime
import traceback
import time
import subprocess
import sys
import traceback

from pathlib import Path
import glob
from .AI_api import tts,llm 
from .config import lora_list,speaker_list,Compliance_Review
from .llm import _call_llm_with_retry, _load_prompt_vars

# 获取当前文件的父目录的父目录（即module1和module2的共同父目录）
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))
from image_api import generate_image
from file_of_film_project import *
from .music_generation import _generate_music_prompts
# ==============================================================================
# 一、 文本预处理模块
# ==============================================================================

def _format_text(project_name):
    """
    智能切分原文，建立章节索引。
    """
    raw_text_path = read_raw_text(project_name)
    
    if not os.path.exists(raw_text_path):
        raise FileNotFoundError(f"原文文件不存在: {raw_text_path}")
        
    with open(raw_text_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    # 1. 尝试正则匹配章节头
    # 匹配 "第x章" 或 "Chapter x" 等，考虑中文数字
    chapter_pattern = r"(第[0-9一二三四五六七八九十百千]+[章|节]|Chapter\s*\d+)"
    matches = list(re.finditer(chapter_pattern, full_text))
    
    chapters = []
    
    if len(matches) > 0:
        # 如果匹配到章节
        for i in range(len(matches)):
            start_idx = matches[i].start()
            # 结束位置是下一个章节的开始，如果是最后一章则是文本末尾
            end_idx = matches[i+1].start() if i < len(matches) - 1 else len(full_text)
            
            # 提取标题和内容
            # 标题通常在 matches[i].group() 中，但可能包含换行，需要清理
            # 这里简单起见，使用章节 ID 自动生成，内容包含标题
            content = full_text[start_idx:end_idx].strip()
            chapter_id = f"chapter_{i+1}"
            chapters.append((chapter_id, content))
    else:
        # 如果未匹配到章节，按字数切分
        chunk_size = 2000
        search_range = 200
        current_pos = 0
        chapter_count = 1
        text_len = len(full_text)
        
        while current_pos < text_len:
            target_pos = current_pos + chunk_size
            
            if target_pos >= text_len:
                cut_pos = text_len
            else:
                # 在 target_pos 前后 search_range 范围内寻找最佳切割点
                search_start = max(current_pos, target_pos - search_range)
                search_end = min(text_len, target_pos + search_range)
                window_text = full_text[search_start:search_end]
                
                # 寻找 \n 或 句号
                # 优先找换行符
                newline_idx = window_text.rfind('\n')
                period_idx = window_text.rfind('。')
                
                if newline_idx != -1:
                    cut_pos = search_start + newline_idx + 1 # 保留换行符
                elif period_idx != -1:
                    cut_pos = search_start + period_idx + 1 # 保留句号
                else:
                    cut_pos = target_pos # 强制切割
            
            content = full_text[current_pos:cut_pos].strip()
            if content:
                chapter_id = f"chapter_{chapter_count}"
                # 自动添加伪标题以便后续识别
                content = f"第 {chapter_count} 部分\n\n{content}"
                chapters.append((chapter_id, content))
                chapter_count += 1
            
            current_pos = cut_pos

    # 存储所有章节
    for ch_id, ch_content in chapters:
        save_chapter(project_name, ch_id, ch_content)
    
    print(f"[{project_name}] 原文处理完成，共切分 {len(chapters)} 章。")

# ==============================================================================
# 二、 摘要生成模块 (Summary System)
# ==============================================================================

def _generate_chapter_summary(project_name):
    """
    生成每章的详细摘要。
    """
    prompt_vars = _load_prompt_vars("_generate_chapter_summary.yaml")
    chapter_ids = get_chapter_list(project_name)
    
    # 按照 ID 排序（假设 ID 格式包含数字或顺序一致，简单排序）
    # 如果 ID 是 "chapter_1", "chapter_2"，字符串排序可能不准，这里假设 get_chapter_list 返回有序列表
    
    for i, chapter_id in enumerate(chapter_ids):
        # 1. 读取文本
        current_text = read_chapter(project_name, chapter_id)
        
        # 上一章摘要
        prev_summary = "无（这是第一章）"
        if i > 0:
            prev_id = chapter_ids[i-1]
            try:
                prev_summary = get_chapter_summary(project_name, prev_id)
            except:
                prev_summary = "（上一章摘要未生成）"
        
        # 下一章预读（截取前 500 字）
        next_preview = "无（这是最后一章）"
        if i < len(chapter_ids) - 1:
            next_id = chapter_ids[i+1]
            next_text = read_chapter(project_name, next_id)
            next_preview = next_text[:500] + "..."
            
        # 2. 构建 Context
        context_data = f"""
### 上下文信息
上一章摘要：
{prev_summary}

### 待处理文本
本章内容：
{current_text}

### 参考信息
下一章预读（仅供连贯性参考，不可剧透）：
{next_preview}
"""
        # 3. 调用 LLM
        # 这里要求输出纯文本，所以 format="text"
        summary = _call_llm_with_retry(prompt_vars, context_data, output_format="text", model_name="Qwen")
        
        # 4. 保存
        save_chapter_summary(project_name, chapter_id, summary)
        print(f"[{project_name}] 章节 {chapter_id} 摘要生成完毕。")


def _generate_summary_on_50_chapters(project_name):
    """
    中层摘要，每50章生成一个聚合摘要。
    """
    prompt_vars = _load_prompt_vars("_generate_summary_on_50_chapters.yaml")
    chapter_ids = get_chapter_list(project_name)
    
    # 分块处理，每 50 章一块
    chunk_size = 50
    chunks = [chapter_ids[i:i + chunk_size] for i in range(0, len(chapter_ids), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        summary_id = f"summary_50_{idx+1}"
        
        # 收集这 50 章的单章摘要
        summaries_text = ""
        for ch_id in chunk:
            try:
                s = get_chapter_summary(project_name, ch_id)
                summaries_text += f"[{ch_id}]: {s}\n\n"
            except:
                continue
        
        context_data = f"""
### 章节摘要列表 ({len(chunk)}章)
{summaries_text}
"""
        # 调用 LLM，要求纯文本
        summary_50 = _call_llm_with_retry(prompt_vars, context_data, output_format="text", model_name="Qwen")
        
        # 保存
        save_summary_on_50_chapters(project_name, summary_id, summary_50)
        print(f"[{project_name}] 50章摘要 {summary_id} 生成完毕。")


def _generate_overall_summary(project_name):
    """
    全书总纲生成，输出 YAML 格式。
    """
    prompt_vars = _load_prompt_vars("_generate_overall_summary.yaml")
    
    # 获取所有 50 章摘要
    summary_50_ids = get_summary_on_50_chapters_list(project_name)
    
    all_summaries_text = ""
    for s_id in summary_50_ids:
        content = get_summary_on_50_chapters(project_name, s_id)
        all_summaries_text += f"[{s_id} 内容]:\n{content}\n\n"
        
    context_data = f"""
### 所有的长篇摘要
{all_summaries_text}
"""
    # 调用 LLM，强制要求 YAML
    overall_data = _call_llm_with_retry(prompt_vars, context_data, output_format="yaml", model_name="Qwen")
    
    # 转换为字符串或直接保存（API save_overall_summary 接受 string 还是 dict？
    # 根据 "save_overall_summary(project_name, summary): 保存到 全文总结.txt"，
    # 以及 prompt 要求 output YAML text。
    # 这里我们把 dict 转回规范的 YAML 字符串保存，或者如果 API 支持 dict 则直接传。
    # 根据通常文件保存逻辑，保存为 yaml 文本比较稳妥。
    
    if isinstance(overall_data, dict):
        overall_text = yaml.dump(overall_data, allow_unicode=True, default_flow_style=False)
    else:
        overall_text = str(overall_data)
        
    save_overall_summary(project_name, overall_text)
    print(f"[{project_name}] 全书总纲生成完毕。")



# ==============================================================================
# 三、 对象分析模块 (Object System)
# ==============================================================================

def _generate_objects(project_name):
    """
    提取角色、场景、物品，并生成带有“状态演变”的详细设定。
    重构后包含三个明确步骤：Extraction -> Ranking -> Profiling
    """
    print(f"[{project_name}] === 开始对象分析流程 ===")

    # 准备数据
    chapter_ids = get_chapter_list(project_name)
    overall_summary = get_overall_summary(project_name)
    
    # -------------------------------------------------------------------------
    # 步骤 1: 海选 (Extraction)
    # -------------------------------------------------------------------------
    print(f"[{project_name}] Step 1: 实体海选 (Extraction)...")
    extraction_prompt_vars = _load_prompt_vars("Extraction.yaml")
    
    # 用于暂存所有提取出的实体，Key=名称，Value={category, aliases, count}
    extracted_pool = {}
    
    # 分批处理 (每 10 章一批)
    batch_size = 10
    chunks = [chapter_ids[i:i + batch_size] for i in range(0, len(chapter_ids), batch_size)]
    
    for idx, batch_ids in enumerate(chunks):
        # 构建当前批次的摘要上下文
        batch_summary_text = ""
        for cid in batch_ids:
            try:
                # 尝试读取章节摘要
                s = get_chapter_summary(project_name, cid)
                batch_summary_text += f"[{cid}]: {s}\n"
            except:
                continue
        
        if not batch_summary_text.strip():
            continue

        context_data = {
            "overall_summary": overall_summary,
            "batch_summary": batch_summary_text
        }
        
        print(f"  - 正在分析第 {idx+1}/{len(chunks)} 批次章节...")
        try:
            # 调用 LLM
            result = _call_llm_with_retry(extraction_prompt_vars, context_data, output_format="yaml", model_name="Qwen")
            
            # 解析结果: 预期结构 {"thoughts": "...", "entities": [...]}
            entities = result.get("entities", [])
            
            # 合并到总池 (简单的名称聚合)
            for entity in entities:
                name = entity.get("name")
                if not name: continue
                
                # 如果池中还没有这个名字，或者当前实体信息更完整，则更新
                if name not in extracted_pool:
                    extracted_pool[name] = {
                        "category": entity.get("category", "未分类"),
                        "aliases": entity.get("aliases", []),
                        "source_chapters": batch_ids # 记录出现的大致范围
                    }
                else:
                    # 合并别名
                    current_aliases = set(extracted_pool[name]["aliases"])
                    new_aliases = set(entity.get("aliases", []))
                    extracted_pool[name]["aliases"] = list(current_aliases.union(new_aliases))
                    extracted_pool[name]["source_chapters"].extend(batch_ids) # 扩展章节记录
                    
        except Exception as e:
            print(f"  - 批次分析失败: {e}")
            continue

    # 去重处理：章节列表去重
    for name in extracted_pool:
        extracted_pool[name]["source_chapters"] = sorted(list(set(extracted_pool[name]["source_chapters"])))

    print(f"  > 海选结束，共提取 {len(extracted_pool)} 个候选实体。")

    # -------------------------------------------------------------------------
    # 步骤 2: 定级 (Ranking)
    # -------------------------------------------------------------------------
    print(f"[{project_name}] Step 2: 实体定级 (Ranking)...")
    ranking_prompt_vars = _load_prompt_vars("Ranking.yaml")
    
    # 构建候选名单字符串
    # 格式： Name (Category)
    entity_list_str = "\n".join([f"- {name} ({data['category']})" for name, data in extracted_pool.items()])
    
    context_data = {
        "overall_summary": overall_summary,
        "entity_list": entity_list_str
    }
    
    rank_result = _call_llm_with_retry(ranking_prompt_vars, context_data, output_format="yaml", model_name="Qwen")
    #print('-'*30)#debug
    #print(rank_result)
    # 预期结构: { "thoughts": "...", "main_objects": [...], "secondary_objects": [...] }
    main_objects_names = rank_result.get("main_objects", [])
    secondary_objects_names = rank_result.get("secondary_objects", [])
    
    # 验证定级结果，如果有遗漏的实体默认归为忽略或次要（此处仅处理 LLM 返回的）
    # 创建 ID 映射并准备保存结构
    # 我们优先处理 Main Objects 赋予较前的 ID
    
    final_objects_to_save = []
    
    def _create_obj_struct(name, is_main=False):
        # 从海选池找回元数据
        pool_data = extracted_pool.get(name, {})
        category = pool_data.get("category", "其他")
        
        # 确定 ID 前缀
        prefix = "obj"
        if "角色" in category: prefix = "char"
        elif "场景" in category: prefix = "loc"
        elif "物品" in category: prefix = "item"
        
        return {
            "name": name,
            "category": category,
            "aliases": pool_data.get("aliases", []),
            "source_chapters": pool_data.get("source_chapters", []),
            "is_main": is_main,
            "id_prefix": prefix
        }
    #print('-'*30)#debug
    #print(main_objects_names)
    for object in main_objects_names:
        name=object['name']
        if name in extracted_pool:
            final_objects_to_save.append(_create_obj_struct(name, is_main=True))
    #print('-'*30)#debug
    #print(secondary_objects_names)
    for object in secondary_objects_names:
        name=object['name']
        if name in extracted_pool:
            final_objects_to_save.append(_create_obj_struct(name, is_main=False))

    print(f"  > 定级完成: {len(main_objects_names)} 个主要对象, {len(secondary_objects_names)} 个次要对象。")

    # -------------------------------------------------------------------------
    # 步骤 3: 状态检测与画像生成 (Profiling)
    # -------------------------------------------------------------------------
    print(f"[{project_name}] Step 3: 详细画像生成 (Profiling)...")
    profiling_prompt_vars = _load_prompt_vars("Profiling & Evolution.yaml")
    
    # 格式化 Lora 列表
    # lora_list 是全局变量 {filename: description}
    lora_list_str = "\n".join([f"- {k} | {v}" for k, v in lora_list.items()])
    
    # 计数器用于生成 ID
    id_counters = {"char": 1, "loc": 1, "item": 1, "obj": 1}
    
    for obj_struct in final_objects_to_save:
        # 生成 ID
        prefix = obj_struct["id_prefix"]
        obj_id = f"{prefix}_{id_counters[prefix]:03d}"
        id_counters[prefix] += 1
        
        name = obj_struct["name"]
        is_main = obj_struct["is_main"]
        
        # 基础数据
        save_data = {
            "名称": name,
            "类型": obj_struct["category"],
            "别名": obj_struct["aliases"],
            "所在章节列表": obj_struct["source_chapters"],
            "is_main_object": is_main
        }
        
        # 只有主要对象才进行昂贵的 Profiling 调用
        # 次要对象只保存基础信息
        if is_main:
            print(f"  - 分析主要对象: {name} ({obj_id})...")
            
            # 构建章节范围描述 (e.g., "chapter_1, chapter_5, ...")
            # 限制长度，防止 token 溢出
            chapter_range_str = ", ".join(obj_struct["source_chapters"][:20])
            if len(obj_struct["source_chapters"]) > 20:
                chapter_range_str += " 等..."

            context_data = {
                "target_object": name,
                "chapter_range": chapter_range_str,
                "overall_summary": overall_summary,
                "lora_list": lora_list_str,
                "speaker_list": json.dumps(speaker_list, ensure_ascii=False)
            }
            
            try:
                # 调用 LLM
                profile_result = _call_llm_with_retry(profiling_prompt_vars, context_data, output_format="yaml")
                
                # 移除 thoughts 字段，保留纯净数据
                if "thoughts" in profile_result:
                    print(f"    [思考] {profile_result.pop('thoughts')}")
                
                # 整合结果到 save_data
                # profile_result 预期包含: object_name, type, default_state, change_states
                
                # 1. 默认状态
                default_state = profile_result.get("default_state", {})
                save_data["描述"] = default_state.get("appearance_cn", "")
                save_data["性格"] = default_state.get("personality", "")
                
                # 构造 standardized states 列表
                # 我们将 default 也视为一种状态，名为 'default'
                states = []
                
                # 添加默认状态
                states.append({
                    "state_name": "default",
                    "visual_description": default_state.get("visual_description", ""),
                    "appearance_prompts": "", # 留给 refinement 阶段翻译或在此处翻译
                    "trigger_keywords": ["通用", "default"], # 默认触发
                    "recommended_lora": default_state.get("recommended_lora", "None"),
                    "lora_weight": default_state.get("lora_weight", 0.8),
                    "speaker": default_state.get("speaker", "narrator")
                })

                
                
                # 添加变化状态
                changes = profile_result.get("states", [])
                if changes:
                    for change in changes:
                        # 清洗 trigger_conditions 为 list
                        triggers = change.get("state_name", "")
                        if isinstance(triggers, str):
                            triggers = [t.strip() for t in triggers.split(",")]
                            
                        states.append({
                            "state_name": change.get("state_name", "unknown_state"),
                            "visual_description": change.get("appearance_cn", ""),
                            "trigger_keywords": triggers,
                            "recommended_lora": change.get("recommended_lora", "None"),
                            "lora_weight": change.get("lora_weight", 0.8),
                            "speaker": change.get("speaker", "narrator")
                        })
                
                save_data["states"] = states
                
            except Exception as e:
                print(f"    ! 对象 {name} 画像生成出错: {e}")
                print(f"错误类型: {type(e).__name__}")
                print(f"错误信息processor at 490: {e}")
                print("错误追踪:")
                traceback.print_exc()  # 打印完整的错误堆栈
                # 出错时保留基础数据，避免 ID 丢失
                save_data["states"] = [{
                    "state_name": "default", 
                    "visual_description": "数据生成失败，仅有占位符。",
                    "trigger_keywords": ["default"]
                }]

        else:
            # 次要对象：仅填充默认占位
            save_data["描述"] = "次要对象，未生成详细画像。"
            save_data["states"] = [{
                "state_name": "default",
                "visual_description": "次要对象",
                "trigger_keywords": ["default"]
            }]
        
        # ---------------------------------------------------------------------
        # 步骤 4: 保存结果
        # ---------------------------------------------------------------------
        save_object(project_name, obj_id, save_data)
        
    print(f"[{project_name}] 对象分析全部完成。")

# ==============================================================================
# 四、 镜头生成模块 (Shot System)
# ==============================================================================
"""
def _process_text_to_shots_blueprint(project_name):
    """
#阶段 1：分镜规划 (Text -> Shot Blueprints)
"""
    print(f"[{project_name}] 开始生成分镜蓝图...")
    prompt_vars = _load_prompt_vars("Shot Blueprint.yaml")
    
    chapter_ids = get_chapter_list(project_name)
    all_objects = list_all_objects(project_name) # [{'名称':..., 'id':..., 'states':...}]
    
    # 构建对象列表字符串，供 Prompt 参考
    objects_list_str = ""
    #print(all_objects)
    for obj_data in all_objects: # list_all_objects 返回 dict {id: data} ? API 文档说是 list dict? 
        # API文档: list_all_objects 返回 对象字典列表。 假设是 List[Dict] 且包含 id 字段，或者 Dict[id, data]
        # 修正：根据 API 文档 `list_all_objects` 返回对象字典列表。我们需要知道 ID。
        # 假设返回 [{...}, {...}]，其中包含我们在 save_object 时未显式存入 id 字段但在读取时可能需要封装。
        # 这里假设 read_object 返回的字典不含 ID，需要我们自己在 save 时处理，或者 list_all_objects 返回 {id: data}。
        # 根据 API 文档风格，通常 list 返回 list。我们假设 list_all_objects 返回的字典里包含我们之前存的 key，或者我们需要用 list_all_objects 配合 keys。
        # 让我们假设 list_all_objects(project_name) 返回 {obj_id: obj_data} 字典结构比较合理。
        obj_id = obj_data.get("id")
        name = obj_data.get("名称")
        states = [s['state_name'] for s in obj_data.get('states', [])]
        if not states: states = ["default"]
        objects_list_str += f"- {name} [{obj_id}] - {states}\n"

    shot_counter = 1 # 全局镜头计数，或者每章重置。API save_shot 接受 shot_id (int)。建议全局累加。
    
    for chapter_id in chapter_ids:
        text = read_chapter(project_name, chapter_id)
        # 切分文本为段落 (每 800 字)
        chunk_size = 800
        text_segments = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        prev_shots_context = "（本章开始）"
        chapter_mood = "根据摘要判断" # 实际可调用 LLM 分析或从摘要获取
        
        for segment in text_segments:
            context_data = {
                "chapter_mood": chapter_mood,
                "prev_shots_context": prev_shots_context,
                "objects_list": objects_list_str,
                "text_segment": segment
            }
            
            # 调用 LLM
            blueprint_result = _call_llm_with_retry(prompt_vars, context_data, output_format="yaml", model_name="DeepSeek")
            #print('-'*30)#debug
            #print(blueprint_result)
            # blueprint_result 预期: [ {id, text_source, type, duration, visual_summary, ...} ]
            shot_list = blueprint_result
            #print('-'*30)#debug
            #print(shot_list)
            for shot in shot_list:
                # 转换 shot 数据以匹配 save_shot 格式
                # 注意：Blueprint 阶段还没有 SD prompt 和 audio info
                #print('-'*30)#debug
                #print(shot)
                # 构造 shot_info
                shot_info = {
                    "text": shot.get("text_source", ""),
                    "type": shot.get("type", "Normal"),
                    "duration": shot.get("duration", 3),
                    "visual_summary": shot.get("visual_summary", ""), # 中文描述
                    "director_demand": shot.get("director_demand", ""),
                    "main_object": shot.get("main_object", ""),
                    "object_state": shot.get("object_state", "default"),
                    "secondary_objects": shot.get("secondary_objects", []),
                    # 预留技术字段
                    "prompt": "", # SD Prompt
                    "script": "", # 语音台词
                    "speaker_id": "",
                    "audio_file": None,
                    "image_file": None
                }
                
                save_shot(project_name, shot_counter, shot_info)
                
                # 更新上下文 (保留最后 3 个镜头的视觉描述)
                prev_shots_context = f"Shot {shot_counter}: {shot_info['visual_summary']}\n" + prev_shots_context
                # 截断 context
                if len(prev_shots_context) > 500: prev_shots_context = prev_shots_context[:500]
                
                shot_counter += 1
                
        print(f"[{project_name}] 章节 {chapter_id} 分镜规划完成。")
"""

def _process_text_to_shots_blueprint(project_name):
    """
    阶段 1：分镜规划 (Text -> Shot Blueprints)
    支持基于镜头表的断点续跑
    """
    print(f"[{project_name}] 开始生成分镜蓝图...")
    prompt_vars = _load_prompt_vars("Shot Blueprint.yaml")

    chapter_ids = get_chapter_list(project_name)
    all_objects = list_all_objects(project_name)

    # ===== 构建对象列表 =====
    objects_list_str = ""
    for obj_data in all_objects:
        obj_id = obj_data.get("id")
        name = obj_data.get("名称")
        states = [s["state_name"] for s in obj_data.get("states", [])] or ["default"]
        objects_list_str += f"- {name} [{obj_id}] - {states}\n"

    # ===== 断点恢复（从镜头表推断）=====
    existing_shots = get_list_shots(project_name)
    shot_counter = (existing_shots[-1] + 1) if existing_shots else 1

    resume_chapter_id = None
    resume_segment_index = 0

    if existing_shots:
        try:
            last_shot = read_shot_info(project_name, existing_shots[-1])
            meta = last_shot.get("blueprint_meta")
            if meta:
                resume_chapter_id = meta.get("chapter_id")
                resume_segment_index = meta.get("segment_index", 0) + 1
        except Exception:
            pass

    # ===== 正式处理 =====
    for chapter_id in chapter_ids:
        if resume_chapter_id is not None and chapter_id < resume_chapter_id:
            continue

        text = read_chapter(project_name, chapter_id)
        chunk_size = 800
        text_segments = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        prev_shots_context = "（本章开始）"
        chapter_mood = "根据摘要判断"

        for segment_index, segment in enumerate(text_segments):
            if (
                resume_chapter_id == chapter_id
                and segment_index < resume_segment_index
            ):
                continue

            context_data = {
                "chapter_mood": chapter_mood,
                "prev_shots_context": prev_shots_context,
                "objects_list": objects_list_str,
                "text_segment": segment
            }

            blueprint_result = _call_llm_with_retry(
                prompt_vars,
                context_data,
                output_format="yaml",
                model_name="DeepSeek"
            )

            for shot in blueprint_result:
                shot_info = {
                    "text": shot.get("text_source", ""),
                    "type": shot.get("type", "Normal"),
                    "duration": shot.get("duration", 3),
                    "visual_summary": shot.get("visual_summary", ""),
                    "director_demand": shot.get("director_demand", ""),
                    "main_object": shot.get("main_object", ""),
                    "object_state": shot.get("object_state", "default"),
                    "secondary_objects": shot.get("secondary_objects", []),

                    # 技术字段
                    "prompt": "",
                    "script": "",
                    "speaker_id": "",
                    "audio_file": None,
                    "image_file": None,

                    # ===== 断点关键字段 =====
                    "blueprint_meta": {
                        "chapter_id": chapter_id,
                        "segment_index": segment_index
                    }
                }

                save_shot(project_name, shot_counter, shot_info)

                prev_shots_context = (
                    f"Shot {shot_counter}: {shot_info['visual_summary']}\n"
                    + prev_shots_context
                )
                if len(prev_shots_context) > 500:
                    prev_shots_context = prev_shots_context[:500]

                shot_counter += 1

        print(f"[{project_name}] 章节 {chapter_id} 分镜规划完成。")


def _refine_shot_technical_details(project_name):
    """
    阶段 2：技术参数填充 (Blueprints -> SD Prompts & Audio Scripts)
    """
    print(f"[{project_name}] 开始生成技术参数...")
    prompt_vars = _load_prompt_vars("Technical Refinement.yaml")
    
    shot_ids = get_list_shots(project_name)
    all_objects = list_all_objects(project_name)
    
    # 构造更详细的对象字典，供查找
    # 假设 list_all_objects 返回 {obj_id: data}
    object_lookup = all_objects 
    
    # 批量处理或逐个处理
    for shot_id in shot_ids:
        shot_info = read_shot_info(project_name, shot_id)
        
        # 如果已经生成过 Prompt，跳过 (支持断点续传)
        if shot_info.get("prompt") and shot_info.get("script"):
            continue
            
        # 准备 Object Details
        # 根据 shot_info['main_object'] 找到对应的对象详细配置
        # 这里存在名字匹配问题。Blueprint 返回的是 name，我们需要 map 到 id 或直接用 name 查
        # 建议在 blueprint 阶段让 LLM 返回 object_id 更稳健，但 prompt 示例是 name。
        # 这里的逻辑：遍历 all_objects 找 name 匹配
        
        target_obj_name = shot_info.get("main_object")
        target_obj_data = {}
        #print('—'*20)
        #print(object_lookup)#debug
        #print('—'*20)
        for odata in object_lookup:
            oid = odata["id"]
            if odata.get("名称") == target_obj_name or target_obj_name in odata.get("别名", []):
                target_obj_data = odata
                break
        
        # 提取特定状态的描述
        state_name = shot_info.get("object_state", "default")
        state_details = "Default Appearance"
        
        if "states" in target_obj_data:
            for s in target_obj_data["states"]:
                if s["state_name"] == state_name:
                    state_details = s
                    break
        
        object_details_str = json.dumps(state_details, ensure_ascii=False)
        
        context_data = {
            "shot_blueprint": json.dumps(shot_info, ensure_ascii=False),
            "object_details": object_details_str,
            "style_lora": "Style Lora: None (Use Base Model Style)", # 全局风格可配置
            "speaker_list": json.dumps(speaker_list, ensure_ascii=False)
        }
        
        # 调用 LLM
        refine_result = _call_llm_with_retry(prompt_vars, context_data, output_format="yaml")
        
        # 更新 shot_info
        update_data = {
            "prompt": refine_result.get("sd_prompt", ""),
            "negative_prompt": refine_result.get("negative_prompt", ""),
            "script": refine_result.get("audio_script", ""),
            "speaker_id": refine_result.get("speaker_id", ""),
            "tts_emotion": refine_result.get("tts_emotion", "neutral")
        }
        
        update_shot_info(project_name, shot_id, update_data)
        
        if shot_id % 10 == 0:
            print(f"[{project_name}] 已处理 {shot_id} 个镜头的技术参数。")


# ==============================================================================
# 六、 主控流程函数
# ==============================================================================

def analyze_text_to_shots(project_name):
    """
    一键执行文本到镜头的全流程。
    """
    try:
        # 1. 文本处理
        # 检查是否已处理过 (简单检查第一章是否存在)
        if not get_chapter_list(project_name):
            _format_text(project_name)
            
        # 2. 摘要生成
        # 检查是否已有摘要
        if get_chapter_summary(project_name, "chapter_1")!=None:
            pass
        else:
            _generate_chapter_summary(project_name)
            _generate_summary_on_50_chapters(project_name)
            _generate_overall_summary(project_name)
            
        # 3. 对象生成
        # 检查对象列表
        #print(list_all_objects(project_name))
        if list_all_objects(project_name) == None:
            _generate_objects(project_name)
            
        # 4. 镜头规划
        #支持断点续传
        _process_text_to_shots_blueprint(project_name)
            
        # 5. 技术参数细化
        # 支持断点续传
        _refine_shot_technical_details(project_name)
            
        # 6. 音乐规划
        _generate_music_prompts(project_name)
        #generate_music(project_name)
        print(f"[{project_name}] 分析流程全部完成。")
        return True
        
    except Exception as e:
        print(f"[{project_name}] 流程中断: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_all(project_name):
    """
    生成所有缺失的素材（图片、语音）。
    """
    shot_ids = get_list_shots(project_name)
    print(f"[{project_name}] 开始生成素材，共 {len(shot_ids)} 个镜头。")
    HighQualitylist=[]
    normallist=[]
    for shot_id in shot_ids:
        shot_info = read_shot_info(project_name, shot_id)
        
        # 1. 图片生成
        if read_shot_image(project_name, shot_id) == None:
            print(f"Generating Image for Shot {shot_id}...")
            prompt = shot_info.get("prompt")
            if prompt:
                # 简单根据 type 决定参数
                width, length = 1024, 576 # 16:9
                if shot_info.get("镜头类型")=="HighQuality":
                    HighQualitylist.append([prompt,shot_id])
                    #img_data = generate_image(prompt, model_name="NoobAI-XL", width=width, height=length)
                else:
                    normallist.append([prompt,shot_id])
                    #img_data = generate_image(prompt, model_name="KOALA-1B", width=width, height=length)
                #save_shot_image(project_name, shot_id, img_data)
        
        # 2. 语音生成
        if read_shot_audio(project_name, shot_id) == None and False:#debug
            script = shot_info.get("script")
            if script and script.strip():
                print(f"Generating Audio for Shot {shot_id}...")
                spk_id = shot_info.get("speaker_id", "narrator")
                audio_data = tts(script, voice_role=spk_id)
                save_shot_audio(project_name, shot_id, audio_data)
    for i in HighQualitylist:
        img_data = generate_image(i[0], model_name="KOALA-1B", width=width, height=length)
        save_shot_image(project_name, i[1], img_data)

    for i in normallist:
        img_data = generate_image(i[0], model_name="KOALA-1B", width=width, height=length)
        save_shot_image(project_name, i[1], img_data)
    print(f"[{project_name}] 素材生成完毕。")
    return True

def generate_video(project_name, force=False):
    """
    生成最终视频文件。
    """
    output_path = os.path.join(ROOT_DIR, project_name, "final_movie.mp4")
    if force:
        analyze_text_to_shots(project_name)
        generate_all(project_name)
        
    shot_ids = get_list_shots(project_name)
    
    temp_dir = os.path.join(ROOT_DIR, project_name, "temp_segments")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    file_list_path = os.path.join(temp_dir, "file_list.txt")
    
    # 先清理旧文件
    for f in glob.glob(os.path.join(temp_dir, "segment_*.mp4")):
        os.remove(f)
    for f in glob.glob(os.path.join(temp_dir, "sub_*.srt")):
        os.remove(f)
    
    with open(file_list_path, 'w', encoding='utf-8') as f_list:
        total_duration = 0
        
        for shot_id in shot_ids:
            shot_dir = get_shot_path(project_name, shot_id)
            
            img_path = os.path.join(shot_dir, "图片.jpg")
            audio_path = os.path.join(shot_dir, "语音.mp3")
            segment_path = os.path.join(temp_dir, f"segment_{shot_id}.mp4")
            
            shot_info = read_shot_info(project_name, shot_id)
            duration = float(shot_info.get("duration", 3.0))
            total_duration += duration
            subtitle_text = shot_info.get("script", "")
            
            has_img = os.path.exists(img_path)
            has_audio = os.path.exists(audio_path)
            
            if not has_img:
                if not force: 
                    raise FileNotFoundError(f"Shot {shot_id} missing image.")
                # 生成黑色背景
                img_path = generate_black_image(temp_dir, shot_id)
                has_img = True
            
            # 1. 首先生成基础视频（无字幕）
            base_video_path = os.path.join(temp_dir, f"base_{shot_id}.mp4")
            
            # 构建基础视频命令
            cmd_base = [
                "ffmpeg", "-y",
                "-loop", "1", 
                "-i", img_path,
                "-t", str(duration)
            ]
            
            if has_audio:
                # 确保音频长度匹配视频长度
                cmd_base += ["-i", audio_path]
                cmd_base += ["-filter_complex", 
                            "[0:a]atrim=0:{}[a1];[1:a]atrim=0:{},apad=pad_dur={}[a2];[a1][a2]amix=inputs=2:duration=first[a]".format(
                                duration, min(duration, get_audio_duration(audio_path)), duration)]
                cmd_base += ["-map", "0:v", "-map", "[a]"]
            else:
                cmd_base += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
                cmd_base += ["-t", str(duration)]
                cmd_base += ["-shortest"]
            
            cmd_base += [
                "-c:v", "libx264", 
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-r", "25",  # 固定帧率
                "-g", "50",  # GOP大小
                "-crf", "23",
            ]
            
            if has_audio:
                cmd_base += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
            else:
                cmd_base += ["-c:a", "aac", "-b:a", "64k", "-ar", "44100"]
                
            cmd_base += ["-movflags", "+faststart", base_video_path]
            
            print(f"生成基础视频片段 {shot_id} (时长: {duration}秒)...")
            try:
                subprocess.run(cmd_base, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"基础视频生成失败: {e.stderr.decode()}")
                continue
            
            # 2. 如果有字幕，添加字幕
            if subtitle_text and subtitle_text.strip():
                subtitle_path = os.path.join(temp_dir, f"sub_{shot_id}.srt")
                
                # 生成SRT字幕文件
                with open(subtitle_path, 'w', encoding='utf-8') as f_srt:
                    # SRT格式的时间
                    start_time = "00:00:00,000"
                    end_time_seconds = int(duration)
                    end_time_ms = int((duration - end_time_seconds) * 1000)
                    end_time = f"00:{end_time_seconds:02d}:{end_time_ms:03d},000"
                    
                    f_srt.write(f"1\n{start_time} --> {end_time}\n{subtitle_text}\n")
                
                # 添加字幕到视频
                cmd_subtitle = [
                    "ffmpeg", "-y",
                    "-i", base_video_path,
                    "-vf", f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=30'",
                    "-c:v", "libx264",
                    "-c:a", "copy",
                    "-preset", "fast",
                    "-crf", "23",
                    segment_path
                ]
                
                print(f"为片段 {shot_id} 添加字幕...")
                try:
                    subprocess.run(cmd_subtitle, check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    print(f"字幕添加失败，使用无字幕版本: {e.stderr.decode()}")
                    os.rename(base_video_path, segment_path)
            else:
                os.rename(base_video_path, segment_path)
            
            # 清理基础视频文件
            if os.path.exists(base_video_path):
                os.remove(base_video_path)
            
            # 写入文件列表
            f_list.write(f"file '{os.path.basename(segment_path)}'\n")
            
            # 验证生成的片段
            if os.path.exists(segment_path):
                try:
                    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                                segment_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True)
                    actual_duration = float(result.stdout.strip())
                    print(f"  实际时长: {actual_duration:.2f}秒 (期望: {duration}秒)")
                except:
                    print(f"  无法验证片段时长")
    
    print(f"\n总期望时长: {total_duration:.2f}秒")
    print(f"合并视频片段...")
    
    # 使用 concat demuxer 合并视频
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", file_list_path,
        "-c", "copy",  # 直接复制流，不重新编码
        "-movflags", "+faststart",  # 优化网络播放
        output_path
    ]
    
    # 首先尝试直接合并
    try:
        print("尝试直接合并...")
        subprocess.run(concat_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"直接合并失败，尝试重新编码合并: {e.stderr.decode()}")
        # 如果直接合并失败，尝试重新编码
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "23",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(concat_cmd, check=True, capture_output=True)
    
    # 验证最终视频
    if os.path.exists(output_path):
        try:
            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                        output_path]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            final_duration = float(result.stdout.strip())
            print(f"\n最终视频信息:")
            print(f"  文件路径: {output_path}")
            print(f"  总时长: {final_duration:.2f}秒")
            print(f"  帧数: {int(final_duration * 25)} 帧 (25fps)")
            
            # 获取视频详细信息
            info_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "stream=width,height,codec_name,r_frame_rate",
                       "-of", "default=noprint_wrappers=1:nokey=1", output_path]
            info_result = subprocess.run(info_cmd, capture_output=True, text=True)
            info_lines = info_result.stdout.strip().split('\n')
            if len(info_lines) >= 4:
                print(f"  分辨率: {info_lines[0]}x{info_lines[1]}")
                print(f"  视频编码: {info_lines[2]}")
                print(f"  帧率: {info_lines[3]}")
        except Exception as e:
            print(f"无法获取视频信息: {e}")
    
    #debug
    # 调试：检查每个视频片段
    for shot_id in shot_ids:
        segment_path = os.path.join(temp_dir, f"segment_{shot_id}.mp4")
        if os.path.exists(segment_path):
            cmd = ["ffprobe", "-v", "error", 
                "-show_entries", "format=duration:stream=duration",
                "-of", "json", segment_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"片段 {shot_id}: {result.stdout}")

    print(f"\n视频生成完成: {output_path}")
    return output_path


def get_audio_duration(audio_path):
    """获取音频文件时长"""
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", 
               "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
               audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0


def generate_black_image(temp_dir, shot_id):
    """生成黑色背景图"""
    img_path = os.path.join(temp_dir, f"black_{shot_id}.jpg")
    if not os.path.exists(img_path):
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", 
            "-i", "color=c=black:s=1024x576",  # 黑色背景
            "-frames:v", "1",
            img_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return img_path


from typing import List, Dict, Any

def save_compliance_report(report_data):
    # 按照需求保存报告
    import os
    save_dir = os.path.join("compliance_reports") # 简化的路径
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{report_data.get('project_name', 'unknown')}_{timestamp}.json"
    filepath = os.path.join(save_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=4)
    print(f"[-] 违规报告已保存至: {filepath}")

# ================= 主逻辑函数 =================



def _Compliance_Review(project_name):
    """
    逐章扫描文本，进行合规性审查。
    利用 _call_llm_with_retry 处理 LLM 交互与容错。
    """
    # 初始化基础报告结构
    report = {
        "success": True,
        "project_name": project_name,
        "scan_start_time": datetime.datetime.now().isoformat(),
        "error_info": {},
        "call_info": {
            "total_chapters": 0,
            "processed_chapters": 0,
            "current_chapter_id": None
        }
    }

    # 收集所有的违规记录
    all_violations = []

    try:
        # 1. 加载提示词配置
        # 直接加载 "Compliance Review.yaml，获取 SYSTEM_PROMPT 和 USER_PROMPT_TEMPLATE
        prompt_vars = _load_prompt_vars("Compliance Review.yaml")
        raw_user_template = prompt_vars.get("USER_PROMPT_TEMPLATE", "")

        # 2. 获取章节列表
        chapter_list = get_chapter_list(project_name)
        report['call_info']['total_chapters'] = len(chapter_list)

        # 3. 逐章扫描
        for chapter_id in chapter_list:
            report['call_info']['current_chapter_id'] = chapter_id
            
            # 读取内容
            content = read_chapter(project_name, chapter_id)
            if not content:
                continue
            
            # 假设章节标题逻辑（如果有专门获取标题的函数可替换此处）
            chapter_title = f"Chapter {chapter_id}"

            # 4. 构建 LLM 请求上下文
            # 注意：您的 _call_llm_with_retry 会将 context_data 拼接到 USER_PROMPT 后面。
            # 但 Prompt 模板中包含 {chapter_title} 占位符。
            # 策略：我们手动格式化模板内容作为 context_data 传入，并将传入 helper 的 template 置空，
            # 这样可以完美利用 helper 的重试逻辑，同时保证 Prompt 格式正确。
            
            formatted_message = raw_user_template.format(
                chapter_title=chapter_title,
                chapter_content=content
            )

            # 创建临时的 prompt 配置，清空模板以避免重复，直接发送格式化好的内容
            runtime_prompt_vars = prompt_vars.copy()
            runtime_prompt_vars["USER_PROMPT_TEMPLATE"] = "" 

            # 5. 调用 LLM (使用提供的容错函数)
            # 虽然提示词要求 JSON，但 yaml.safe_load 兼容 JSON，所以保持 output_format="yaml" 即可复用解析逻辑
            llm_result = _call_llm_with_retry(
                prompt_vars=runtime_prompt_vars,
                context_data=formatted_message, 
                output_format="yaml",
                model_name="Qwen"
            )

            # 6. 解析结果并处理
            # _call_llm_with_retry 已经返回了解析后的字典
            if isinstance(llm_result, dict):
                is_compliant = llm_result.get("is_compliant", True)
                
                if not is_compliant:
                    violations = llm_result.get("violations", [])
                    for v in violations:
                        # 补充元数据
                        record = {
                            "chapter_id": chapter_id,
                            "chapter_title": chapter_title,
                            "violation_content": v.get("quote", ""),
                            "violation_reason": v.get("reason", ""),
                            "violation_category": v.get("category", ""),
                            "violation_time": datetime.datetime.now().isoformat()
                        }
                        all_violations.append(record)
            
            report['call_info']['processed_chapters'] += 1

        # 7. 如果发现违规，生成并保存详细报告
        if all_violations:
            compliance_report_data = {
                "project_name": project_name,
                "report_time": datetime.datetime.now().isoformat(),
                "total_violations": len(all_violations),
                "details": all_violations
            }
            save_compliance_report(compliance_report_data)
        
        report["scan_end_time"] = datetime.datetime.now().isoformat()
        report["violation_count"] = len(all_violations)

    except Exception as e:
        # 8. 错误捕获与现场还原
        report["success"] = False
        report["error_info"] = {
            "error_reason": str(e),
            "error_time": datetime.datetime.now().isoformat(),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc() # 完整堆栈
        }
        # 记录最后处理的状态，方便调试
        print(f"[-] Compliance Review Failed: {e}")

    return report


