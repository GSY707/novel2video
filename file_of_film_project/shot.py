import uuid
from .config import _get_project_dir
from .utils import _save_yaml, _load_yaml, _ensure_dir, _save_binary, _read_binary
import os
import shutil

def _resolve_shot_path(project_name, shot_id, create_if_new=False):
    """
    核心函数：将逻辑 shot_id (int) 转换为物理路径
    shot_id: 1, 2, 3...
    return: (physical_folder_path, is_newly_created)
    """
    sequence = _get_shot_sequence(project_name)
    
    # 转换为 0-based index
    try:
        index = int(shot_id) - 1
    except ValueError:
        return None, False

    if index < 0:
        return None, False

    # 如果ID存在于当前列表中
    if index < len(sequence):
        folder_name = sequence[index]
        return os.path.join(_get_project_dir(project_name), "镜头", folder_name), False
    
    # 如果是新建镜头 (通常由 save_shot 调用)
    if create_if_new:
        # 生成唯一的物理文件夹名称
        folder_name = f"镜头_{uuid.uuid4().hex[:8]}" 
        # 这里处理一种情况：如果用户想存 shot_id=5，但当前只有 2 个镜头。
        # 简单策略：填充中间的空缺，或者强制追加。
        # 这里假设 save_shot 应该按顺序调用，或者我们直接追加到末尾。
        # 为了符合 edit_shot_sequence 的逻辑，我们直接追加并返回新路径。
        #print('—'*20)
        #print(sequence)#debug
        #print('—'*20)
        sequence[index]=folder_name
        _save_shot_sequence(project_name, sequence)
        
        full_path = os.path.join(_get_project_dir(project_name), "镜头", folder_name)
        _ensure_dir(full_path)
        return full_path, True

    return None, False

def _get_sequence_path(project_name):
    # 后缀改为 yaml
    return os.path.join(_get_project_dir(project_name), "镜头", "镜头顺序.yaml")

def _get_shot_sequence(project_name):
    path = _get_sequence_path(project_name)
    # 使用 yaml 读取
    return _load_yaml(path) if os.path.exists(path) else []

def _save_shot_sequence(project_name, sequence_list):
    path = _get_sequence_path(project_name)
    # 使用 yaml 保存
    _save_yaml(path, sequence_list)

# _resolve_shot_path 逻辑保持不变，它只负责找文件夹路径

def save_shot(project_name, shot_id, shot_info):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id, create_if_new=True)
    if not shot_dir: return None

    # 修改：文件名改为 镜头内容.yaml
    yaml_path = os.path.join(shot_dir, "镜头内容.yaml")
    
    content_data = {

        "镜头图片提示词": shot_info.get("prompt", ""),
        "镜头视频提示词": shot_info.get("video_prompt", ""),
        "镜头原文": shot_info.get("text", ""),
        "镜头表达需求": shot_info.get("director_demand", ""),
        "镜头音频生成设置": shot_info.get("speaker_id", ""),
        "镜头台词或旁白": shot_info.get("script", ""),
        "镜头类型": shot_info.get("type", "一般镜头"),
        "镜头描述": shot_info.get("visual_summary", ""),
        "时长": shot_info.get("duration", 3),
        "主要对象": shot_info.get("main_object", ""),
        "主要对象状态": shot_info.get("object_state", "default"),
        "次要对象": shot_info.get("secondary_objects", []),
    }
    _save_yaml(yaml_path, content_data)
    return None

def update_shot_info(project_name, shot_id, shot_info):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if not shot_dir: return None
    
    yaml_path = os.path.join(shot_dir, "镜头内容.yaml")
    current_data = _load_yaml(yaml_path)
    current_data.update(shot_info)
    _save_yaml(yaml_path, current_data)
    return None

def read_shot_info(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if not shot_dir: return {}
    yaml_path = os.path.join(shot_dir, "镜头内容.yaml")
    return _load_yaml(yaml_path)

def delete_shot(project_name, shot_id):
    """
    删除镜头：
    1. 删除物理文件夹
    2. 从顺序列表中移除（后续镜头的ID会前移）
    """
    sequence = _get_shot_sequence(project_name)
    try:
        index = int(shot_id) - 1
        if 0 <= index < len(sequence):
            folder_name = sequence[index]
            shot_dir = os.path.join(_get_project_dir(project_name), "镜头", folder_name)
            
            # 删除物理文件
            if os.path.exists(shot_dir):
                shutil.rmtree(shot_dir)
            
            # 更新列表
            del sequence[index]
            _save_shot_sequence(project_name, sequence)
    except ValueError:
        pass
    return None

def get_list_shots(project_name):
    """
    返回镜头ID列表。
    现在只需要返回逻辑ID列表 [1, 2, 3, ...]
    """
    sequence = _get_shot_sequence(project_name)
    # 生成从 1 到 N 的列表
    return list(range(1, len(sequence) + 1))

def save_shot_image(project_name, shot_id, image_data):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "图片.jpg")
        _save_binary(file_path, image_data)
    return None

def read_shot_image(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "图片.jpg")
        return _read_binary(file_path)
    return None

def get_shot_path(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        return shot_dir
    return None

def delete_shot_image(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "图片.jpg")
        if os.path.exists(file_path):
            os.remove(file_path)
    return None

def save_shot_audio(project_name, shot_id, audio_data):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "语音.mp3")
        _save_binary(file_path, audio_data)
    return None

def read_shot_audio(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "语音.mp3")
        return _read_binary(file_path)
    return None

def delete_shot_audio(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "语音.mp3")
        if os.path.exists(file_path):
            os.remove(file_path)
    return None

def save_shot_video(project_name, shot_id, video_data):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "视频.mp4")
        _save_binary(file_path, video_data)
    return None

def read_shot_video(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "视频.mp4")
        return _read_binary(file_path)
    return None

def delete_shot_video(project_name, shot_id):
    shot_dir, _ = _resolve_shot_path(project_name, shot_id)
    if shot_dir:
        file_path = os.path.join(shot_dir, "视频.mp4")
        if os.path.exists(file_path):
            os.remove(file_path)
    return None

def edit_shot_sequence(project_name, new_sequence_list):
    """
    修改镜头顺序。
    input: new_sequence_list = [4, 1, 2, 3] (代表旧的逻辑ID的排列顺序)
    逻辑：
    1. 获取当前的物理文件夹列表 (例如 [FolderA, FolderB, FolderC, FolderD])
    2. 根据输入的旧ID列表，重新排列这个物理文件夹列表。
       旧ID 4 (Index 3) -> FolderD
       旧ID 1 (Index 0) -> FolderA
    3. 保存新的列表 -> [FolderD, FolderA, FolderB, FolderC]
    """
    current_sequence = _get_shot_sequence(project_name)
    if not current_sequence:
        return None

    new_physical_order = []
    
    for old_logical_id in new_sequence_list:
        try:
            # 逻辑ID转索引 (1-based -> 0-based)
            index = int(old_logical_id) - 1
            if 0 <= index < len(current_sequence):
                new_physical_order.append(current_sequence[index])
            else:
                # 如果传入了越界的ID，为了防止数据丢失，这里需要处理错误
                # 简单处理：跳过或报错。这里选择跳过。
                pass 
        except ValueError:
            pass
            
    # 安全检查：确保重排后的长度与原来一致，防止误删镜头
    # 如果长度不一致，说明 new_sequence_list 有问题（比如有重复ID或缺少ID）
    # 这里做一个简单的去重补全逻辑，或者直接覆盖（取决于你的业务可信度）
    # 为保证安全，如果数量对不上，建议不做更改
    if len(new_physical_order) == len(current_sequence):
        _save_shot_sequence(project_name, new_physical_order)
    else:
        print(f"Error: Sequence length mismatch. Expected {len(current_sequence)}, got {len(new_physical_order)}")
        return None

    return None