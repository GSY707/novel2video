from .config import _get_project_dir
import os
from .utils import _load_yaml, _save_yaml, _save_binary, _read_binary


def _get_music_list_path(project_name):
    # 文件名从 提示词.json 改为 音乐列表.yaml，更符合直觉
    return os.path.join(_get_project_dir(project_name), "音乐", "音乐列表.yaml")

def save_music_prompt(project_name, music_id, prompt):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    
    if music_id not in data: data[music_id] = {}
    data[music_id]["音乐prompt"] = prompt
    
    _save_yaml(path, data)
    return None

def read_music_prompt(project_name, music_id):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    return data.get(music_id, {}).get("音乐prompt", None)

def delete_music_prompt(project_name, music_id):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    if music_id in data and "音乐prompt" in data[music_id]:
        # 设为空字符串或删除key，这里选择设为空
        data[music_id]["音乐prompt"] = "" 
        _save_yaml(path, data)
    return None

def save_music_content(project_name, music_id, content):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    if music_id not in data: data[music_id] = {}
    data[music_id]["音乐内容"] = content
    _save_yaml(path, data)
    return None

def read_music_content(project_name, music_id):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    return data.get(music_id, {}).get("音乐内容", None)

def delete_music_content(project_name, music_id):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    if music_id in data:
        data[music_id]["音乐内容"] = ""
        _save_yaml(path, data)
    return None

def get_all_music_ids(project_name):
    path = _get_music_list_path(project_name)
    data = _load_yaml(path)
    return list(data.keys())

def save_music_audio(project_name, music_id, music_audio_data):
    # 强制使用 .mp3
    filename = f"{music_id}.mp3" 
    file_path = os.path.join(_get_project_dir(project_name), "音乐", filename)
    _save_binary(file_path, music_audio_data)
    return None

def read_music_audio(project_name, music_id):
    filename = f"{music_id}.mp3"
    file_path = os.path.join(_get_project_dir(project_name), "音乐", filename)
    return _read_binary(file_path)

def delete_music_audio(project_name, music_id):
    filename = f"{music_id}.mp3"
    file_path = os.path.join(_get_project_dir(project_name), "音乐", filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return None
