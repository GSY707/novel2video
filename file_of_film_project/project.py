from .config import _get_project_dir , ROOT_DIR
import os
import shutil
from .utils import _ensure_dir, _load_yaml, _save_yaml

def _init_object_yaml_structure():
    return {
        "基本信息": {
            "总对象数": 0, "场景数": 0, "物品数": 0, "角色数": 0, "其他对象数": 0
        },
        "分类数据": {
            "场景": {}, "物品": {}, "角色": {}, "其他对象": {}
        }
    }

def get_project_folder(project_name):
    """返回项目文件夹的绝对路径"""
    path = _get_project_dir(project_name)
    if os.path.exists(path):
        return os.path.abspath(path)
    return None

def delete_project_folder(project_name):
    """删除整个项目"""
    path = _get_project_dir(project_name)
    if os.path.exists(path):
        shutil.rmtree(path)
    return None

def list_all_projects():
    """
    列出ROOT_DIR下所有的项目名称
    """
    if not os.path.exists(ROOT_DIR):
        return []
    # 过滤出文件夹作为项目名
    projects_list = [
        d for d in os.listdir(ROOT_DIR) 
        if os.path.isdir(os.path.join(ROOT_DIR, d))
    ]
    return projects_list

def read_project_info(project_name):
    path = os.path.join(_get_project_dir(project_name), "project_config.yaml")
    # 兼容旧版 json (如果存在旧版json，读取并尝试迁移，这里简化为只读 yaml)
    # 如果项目是新建的，直接读 yaml
    return _load_yaml(path)

def edit_project_info(project_name, info):
    path = os.path.join(_get_project_dir(project_name), "project_config.yaml")
    data = _load_yaml(path)
    data.update(info)
    _save_yaml(path, data)
    return None

def create_project_folder(project_name):
    base_path = _get_project_dir(project_name)
    
    # 1. 创建文件夹结构 (增加 对象)
    folders = ["文本", "镜头", "音乐", "未使用图片", "对象", "对象/对象图片"]
    for f in folders:
        _ensure_dir(os.path.join(base_path, f))
        
    # 2. 初始化 对象列表.yaml
    obj_path = os.path.join(base_path, "对象", "对象列表.yaml")
    if not os.path.exists(obj_path):
        _save_yaml(obj_path, _init_object_yaml_structure())

    # 3. 初始化 镜头顺序.yaml (原json)
    shot_seq_path = os.path.join(base_path, "镜头", "镜头顺序.yaml")
    if not os.path.exists(shot_seq_path):
        _save_yaml(shot_seq_path, []) # 空列表

    # 4. 初始化 项目配置 project_config.yaml (原 项目名.json)
    settings_path = os.path.join(base_path, "project_config.yaml")
    if not os.path.exists(settings_path):
        init_settings = {
            "视频分辨率": {"视频长度": 1024, "视频宽度": 576},
            "保留字段": {}
        }
        _save_yaml(settings_path, init_settings)
        
    return None