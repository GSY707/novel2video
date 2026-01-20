from .config import _get_project_dir
import os
from .utils import _load_yaml, _save_yaml, _read_binary, _save_binary

def _get_object_yaml_path(project_name):
    return os.path.join(_get_project_dir(project_name), "对象", "对象列表.yaml")

def _init_object_yaml_structure():
    return {
        "基本信息": {
            "总对象数": 0, "场景数": 0, "物品数": 0, "角色数": 0, "其他对象数": 0
        },
        "分类数据": {
            "场景": {}, "物品": {}, "角色": {}, "其他对象": {}
        }
    }

def _update_object_counts(data):
    """更新统计信息"""
    counts = data.get("基本信息", {})
    categories = data.get("分类数据", {})
    total = 0
    for key in ["场景", "物品", "角色", "其他对象"]:
        # 确保键存在
        if key not in categories: categories[key] = {}
        c = len(categories[key])
        counts[f"{key}数"] = c
        total += c
    counts["总对象数"] = total
    data["基本信息"] = counts
    return data

def save_object(project_name, object_id, object_data):
    yaml_path = _get_object_yaml_path(project_name)
    data = _load_yaml(yaml_path)
    if not data: data = _init_object_yaml_structure()

    # 确定类型，默认为其他对象
    obj_type = object_data.get("类型", "其他对象")
    valid_types = ["场景", "物品", "角色", "其他对象"]
    if obj_type not in valid_types: obj_type = "其他对象"

    # 清理旧数据（防止修改类型后ID重复存在于两个分类下）
    for t in valid_types:
        if t != obj_type and object_id in data["分类数据"].get(t, {}):
            del data["分类数据"][t][object_id]

    # 保存新数据
    if obj_type not in data["分类数据"]: 
        data["分类数据"][obj_type] = {}
    
    data["分类数据"][obj_type][object_id] = object_data
    
    data = _update_object_counts(data)
    _save_yaml(yaml_path, data)
    return None

def read_object(project_name, object_id):
    yaml_path = _get_object_yaml_path(project_name)
    data = _load_yaml(yaml_path)
    categories = data.get("分类数据", {})
    
    for cat_type, items in categories.items():
        if object_id in items:
            res = items[object_id].copy()
            res["类型"] = cat_type # 补充类型信息
            return res
    return None

def delete_object(project_name, object_id):
    yaml_path = _get_object_yaml_path(project_name)
    data = _load_yaml(yaml_path)
    categories = data.get("分类数据", {})
    
    deleted = False
    for cat_type, items in categories.items():
        if object_id in items:
            del items[object_id]
            deleted = True
            break
            
    if deleted:
        data = _update_object_counts(data)
        _save_yaml(yaml_path, data)
        # 级联删除图片
        delete_object_image(project_name, object_id)
    return None

def list_all_objects(project_name, obj_type=None):
    yaml_path = _get_object_yaml_path(project_name)
    data = _load_yaml(yaml_path)
    categories = data.get("分类数据", {})
    
    result = []
    # 辅助函数：提取列表
    def extract(t):
        items = categories.get(t, {})
        for oid, v in items.items():
            temp = v.copy()
            temp['id'] = oid
            temp['类型'] = t
            result.append(temp)

    if obj_type:
        extract(obj_type)
    else:
        for t in ["场景", "物品", "角色", "其他对象"]:
            extract(t)
            
    return result

def save_object_image(project_name, object_id, image_data):
    # 假设统一存储为 jpg
    filename = f"{object_id}.jpg"
    path = os.path.join(_get_project_dir(project_name), "对象", "对象图片", filename)
    _save_binary(path, image_data)
    
    # 更新yaml中的图片引用
    obj = read_object(project_name, object_id)
    if obj:
        obj["对象图片名"] = filename
        save_object(project_name, object_id, obj)
    return None

def read_object_image(project_name, object_id):
    filename = f"{object_id}.jpg"
    path = os.path.join(_get_project_dir(project_name), "对象", "对象图片", filename)
    return _read_binary(path)

def delete_object_image(project_name, object_id):
    filename = f"{object_id}.jpg"
    path = os.path.join(_get_project_dir(project_name), "对象", "对象图片", filename)
    if os.path.exists(path):
        os.remove(path)
    
    # 清除引用
    obj = read_object(project_name, object_id)
    if obj and "对象图片名" in obj:
        obj["对象图片名"] = ""
        save_object(project_name, object_id, obj)
    return None

def read_object_on_chapter(project_name, chapter_id):
    """读取该章节关联的所有对象"""
    all_objs = list_all_objects(project_name)
    res = []
    s_cid = str(chapter_id)
    for obj in all_objs:
        # 兼容不同可能的字段命名
        chapters = obj.get("所在章节列表", []) or obj.get("对象所在章节列表", [])
        # 确保转字符串比较
        if s_cid in [str(x) for x in chapters]:
            res.append(obj)
    return res