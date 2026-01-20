from .config import _get_project_dir
import os
from .utils import _save_binary, _read_binary

def get_unused_images_list(project_name):
    img_dir = os.path.join(_get_project_dir(project_name), "未使用图片")
    if not os.path.exists(img_dir):
        return []
    return [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f))]

def save_unused_image(project_name, image_data):
    """
    保存未使用图片。
    注意：API 没有传入 image_id，需要自动生成一个。
    这里使用简单的UUID或时间戳。
    """
    import uuid
    image_id = str(uuid.uuid4()) + ".jpg"
    file_path = os.path.join(_get_project_dir(project_name), "未使用图片", image_id)
    _save_binary(file_path, image_data)
    return None

def read_unused_image(project_name, image_id):
    file_path = os.path.join(_get_project_dir(project_name), "未使用图片", image_id)
    return _read_binary(file_path)

def delete_unused_image(project_name, image_id):
    file_path = os.path.join(_get_project_dir(project_name), "未使用图片", image_id)
    if os.path.exists(file_path):
        os.remove(file_path)
    return None