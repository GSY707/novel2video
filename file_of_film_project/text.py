from .config import _get_project_dir
import os
from .utils import _load_json, _save_json, _read_text_file, _save_text_file

def read_raw_text(project_name):
    """
    返回原文.txt的完整路径地址
    """
    # 对应结构: 项目名/文本/原文.txt
    file_path = os.path.join(_get_project_dir(project_name), "文本", "原文.txt")
    if os.path.exists(file_path):
        return os.path.abspath(file_path)
    return None

def save_raw_text(project_name, text):
    file_path = os.path.join(_get_project_dir(project_name), "文本", "原文.txt")
    _save_text_file(file_path, text)
    return None

def read_chapter(project_name, chapter_id):
    """
    注意：章节内容存储在'格式化.json'中。
    这里返回具体的章节内容文本(String)，而不是文件地址，
    因为单个章节没有独立文件。
    """
    json_path = os.path.join(_get_project_dir(project_name), "文本", "格式化.json")
    data = _load_json(json_path)
    # 根据描述：格式化.json -> 章节id: 章节内容
    return data.get(chapter_id, None)

def save_chapter(project_name, chapter_id, text):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "格式化.json")
    data = _load_json(json_path)
    
    data[chapter_id] = text
    # 更新计数，排除 counts 键本身
    chapter_keys = [k for k in data.keys() if k != 'counts']
    data['counts'] = len(chapter_keys)
    
    _save_json(json_path, data)
    return None

def get_chapter_list(project_name):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "格式化.json")
    data = _load_json(json_path)
    # 返回除 counts 以外的所有键 (即章节ID)
    return [k for k in data.keys() if k != 'counts']

def delete_chapter(project_name, chapter_id):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "格式化.json")
    data = _load_json(json_path)
    if chapter_id in data:
        del data[chapter_id]
        chapter_keys = [k for k in data.keys() if k != 'counts']
        data['counts'] = len(chapter_keys)
        _save_json(json_path, data)
    return None

def get_chapter_summary(project_name, chapter_id):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每章总结.json")
    data = _load_json(json_path)
    return data.get(chapter_id, None)

def save_chapter_summary(project_name, chapter_id, summary):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每章总结.json")
    data = _load_json(json_path)
    data[chapter_id] = summary
    chapter_keys = [k for k in data.keys() if k != 'counts']
    data['counts'] = len(chapter_keys)
    _save_json(json_path, data)
    return None

def delete_chapter_summary(project_name, chapter_id):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每章总结.json")
    data = _load_json(json_path)
    if chapter_id in data:
        del data[chapter_id]
        chapter_keys = [k for k in data.keys() if k != 'counts']
        data['counts'] = len(chapter_keys)
        _save_json(json_path, data)
    return None

def get_summary_on_50_chapters(project_name, summary_on_50_ids):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每50章总结.json")
    data = _load_json(json_path)
    return data.get(summary_on_50_ids, None)

def get_summary_on_50_chapters_list(project_name):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每50章总结.json")
    data = _load_json(json_path)
    # 返回除 counts 以外的所有键 (即章节ID)
    return [k for k in data.keys() if k != 'counts']

def save_summary_on_50_chapters(project_name, summary_on_50_ids, summaries):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每50章总结.json")
    data = _load_json(json_path)
    data[summary_on_50_ids] = summaries
    keys = [k for k in data.keys() if k != 'counts']
    data['counts'] = len(keys)
    _save_json(json_path, data)
    return None

def delete_summary_on_50_chapters(project_name, summary_on_50_ids):
    json_path = os.path.join(_get_project_dir(project_name), "文本", "每50章总结.json")
    data = _load_json(json_path)
    if summary_on_50_ids in data:
        del data[summary_on_50_ids]
        keys = [k for k in data.keys() if k != 'counts']
        data['counts'] = len(keys)
        _save_json(json_path, data)
    return None

def get_overall_summary(project_name):
    file_path = os.path.join(_get_project_dir(project_name), "文本", "全文总结.txt")
    return _read_text_file(file_path)

def save_overall_summary(project_name, summary):
    file_path = os.path.join(_get_project_dir(project_name), "文本", "全文总结.txt")
    _save_text_file(file_path, summary)
    return None

def delete_overall_summary(project_name):
    file_path = os.path.join(_get_project_dir(project_name), "文本", "全文总结.txt")
    if os.path.exists(file_path):
        os.remove(file_path)
    return None
