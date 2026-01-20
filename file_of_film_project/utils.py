import os
import json
import shutil
import yaml

def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def _save_json(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def _save_binary(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, 'wb') as f:
        f.write(data)

def _read_binary(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return f.read()
    return None

def _read_text_file(path):
    """读取纯文本文件"""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def _save_text_file(path, text):
    """保存纯文本文件"""
    _ensure_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def _load_yaml(path):
    """读取YAML文件，失败返回空字典"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _save_yaml(path, data):
    """保存YAML文件，强制使用更易读的块格式"""
    _ensure_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        # allow_unicode=True 显示中文，sort_keys=False 保持插入顺序
        # default_flow_style=False 强制使用块状格式而不是行内大括号
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)