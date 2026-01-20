# 项目文件管理系统 API 文档

## 1. 简介与配置

本模块提供了一套基于文件系统的API，用于管理视频生成项目的各类资源。数据以 JSON、YAML 和二进制文件（图片/音视频）的形式存储在本地硬盘。

### 依赖库
使用前请确保安装 PyYAML：
```bash
pip install pyyaml
```

### 全局配置
在使用前，请在代码顶部修改 `ROOT_DIR` 变量，指向您的工作区根目录：
```python
ROOT_DIR = "C:\web\project_files" # 请根据实际环境修改
```
导入本模块：
```python
import file_of_film_project
```
---

## 2. 项目管理 (Project Management)

用于创建、列出和配置项目。

### `create_project_folder(project_name)`
初始化一个新的项目文件夹结构。
*   **参数**: `project_name` (str) - 项目名称
*   **功能**: 创建文本、镜头、音乐、对象等子目录，并初始化必要的 YAML 配置文件。

### `list_all_projects()`
*   **返回**: `list[str]` - `ROOT_DIR` 下所有项目的名称列表。

### `get_project_folder(project_name)`
*   **返回**: `str` - 项目的绝对物理路径。

### `delete_project_folder(project_name)`
*   **功能**: 彻底删除指定项目文件夹及其所有内容。

### `read_project_info(project_name)`
读取项目配置信息（如视频分辨率等）。
*   **返回**: `dict` - 配置字典。

### `edit_project_info(project_name, info)`
更新项目配置。
*   **参数**: `info` (dict) - 要更新的配置键值对。

---

## 3. 文本系统 (Text System)

管理原文、章节切分及总结。

### 原文管理
*   **`save_raw_text(project_name, text)`**: 保存项目原本（原文.txt）。
*   **`read_raw_text(project_name)`**: 返回原文文件的**绝对路径**（注意：不是返回内容，是返回路径）。

### 章节内容
章节内容存储在 `文本/格式化.json` 中。

*   **`save_chapter(project_name, chapter_id, text)`**: 保存特定章节的内容。会自动更新章节计数。
*   **`read_chapter(project_name, chapter_id)`**: 返回章节文本内容 (str)。
*   **`get_chapter_list(project_name)`**: 返回所有章节ID的列表。
*   **`delete_chapter(project_name, chapter_id)`**: 删除指定章节。

### 总结管理
*   **单章总结**:
    *   `save_chapter_summary(project_name, chapter_id, summary)`
    *   `get_chapter_summary(project_name, chapter_id)`
    *   `delete_chapter_summary(project_name, chapter_id)`
*   **50章长总结**:
    *   `save_summary_on_50_chapters(project_name, summary_id, summaries)`
    *   `get_summary_on_50_chapters_list(project_name)`**: 返回所有50章总结的ID的列表。
    *   `get_summary_on_50_chapters(project_name, summary_id)`
*   **全文总结**:
    *   `save_overall_summary(project_name, summary)`: 保存到 `全文总结.txt`。
    *   `get_overall_summary(project_name)`: 读取全文总结内容。

---

## 4. 镜头系统 (Shot System)

核心功能。镜头以文件夹形式存储，包含 YAML 配置和媒体文件。API 内部维护一个逻辑 ID (1, 2, 3...) 到物理文件夹名的映射。

### 镜头信息管理
*   **`save_shot(project_name, shot_id, shot_info)`**
    *   **功能**: 创建或保存镜头信息。如果 `shot_id` 对应的镜头不存在，会自动创建物理文件夹。
    *   **shot_info 结构示例**:
        ```python
        {
            "prompt": "画面提示词",
            "video_prompt": "视频提示词",
            "text": "镜头内容描述",
            "demand": "表达需求",
            "speaker_id": "配音员ID",
            "script": "台词",
            "type": "一般镜头"
        }
        ```
*   **`update_shot_info(project_name, shot_id, shot_info)`**: 更新现有镜头的 YAML 信息。
*   **`read_shot_info(project_name, shot_id)`**: 读取镜头信息字典。
*   **`delete_shot(project_name, shot_id)`**: 删除镜头文件夹并更新顺序列表。
*   **`get_list_shots(project_name)`**: 返回当前所有镜头的逻辑 ID 列表（如 `[1, 2, 3]`）。

### 镜头顺序编辑
*   **`edit_shot_sequence(project_name, new_sequence_list)`**
    *   **功能**: 重新排列镜头顺序。
    *   **参数**: `new_sequence_list` (list[int]) - 旧逻辑 ID 的新排列顺序。
    *   **示例**: 如果当前有 3 个镜头 [1, 2, 3]，想把第 3 个移到第 1 位，传入 `[3, 1, 2]`。物理文件夹会据此重排。

### 镜头素材 (媒体文件)
所有媒体数据均为**二进制数据 (bytes)**。

*   **图片**:
    *   `save_shot_image(project_name, shot_id, image_data)`: 保存为 `图片.jpg`。
    *   `read_shot_image(project_name, shot_id)`
    *   `delete_shot_image(project_name, shot_id)`
*   **语音**:
    *   `save_shot_audio(project_name, shot_id, audio_data)`: 保存为 `语音.mp3`。
    *   `read_shot_audio(project_name, shot_id)`
    *   `delete_shot_audio(project_name, shot_id)`
*   **视频**:
    *   `save_shot_video(project_name, shot_id, video_data)`: 保存为 `视频.mp4`。
    *   `read_shot_video(project_name, shot_id)`
    *   `delete_shot_video(project_name, shot_id)`

---

## 5. 对象系统 (Object System)

管理角色、场景、物品等。所有对象存储在同一个 `对象列表.yaml` 中，图片存储在 `对象/对象图片` 目录。

### 对象数据
*   **`save_object(project_name, object_id, object_data)`**
    *   **object_data 关键字段**:
        *   `"类型"`: 必须是 ["场景", "物品", "角色", "其他对象"] 之一，默认为 "其他对象"。
        *   `"所在章节列表"`: list，用于通过章节查询对象。
*   **`read_object(project_name, object_id)`**: 读取对象详情，返回字典中会自动包含 `"类型"` 字段。
*   **`delete_object(project_name, object_id)`**: 删除对象记录及其关联图片。
*   **`list_all_objects(project_name, obj_type=None)`**
    *   **参数**: `obj_type` (可选) - 筛选特定类型（"角色", "场景"等）。
    *   **返回**: 对象字典列表。
*   **`read_object_on_chapter(project_name, chapter_id)`**: 返回该章节关联的所有对象列表。

### 对象图片
*   **`save_object_image(project_name, object_id, image_data)`**: 保存图片并自动在 YAML 中更新引用。
*   **`read_object_image(project_name, object_id)`**: 读取二进制图片数据。
*   **`delete_object_image(project_name, object_id)`**: 删除图片文件并清除引用。

---

## 6. 音乐系统 (Music System)

*   **ID**: `music_id` 由用户自定义。
*   **Prompt/内容**:
    *   `save_music_prompt`, `read_music_prompt`, `delete_music_prompt`
    *   `save_music_content`, `read_music_content`, `delete_music_content`
*   **音频文件**:
    *   `save_music_audio(..., music_audio_data)`: 保存为 `{music_id}.mp3`。
    *   `read_music_audio(...)`, `delete_music_audio(...)`
*   **列表**:
    *   `get_all_music_ids(project_name)`: 获取所有音乐 ID。

---

## 7. 未使用图片 (Unused Images)

用于存放临时生成的图片素材。

*   **`save_unused_image(project_name, image_data)`**: 自动生成 UUID 文件名保存。
*   **`get_unused_images_list(project_name)`**: 获取所有未使用图片的文件名列表。
*   **`read_unused_image(project_name, image_id)`**: 读取图片数据。
*   **`delete_unused_image(project_name, image_id)`**: 删除图片。

---

## 8. 调用示例

```python
# 1. 初始化项目
project = "DemoMovie"
create_project_folder(project)

# 2. 保存章节文本
chapter_text = "这是一个漆黑的夜晚，主角小明站在路灯下..."
save_chapter(project, "chapter_1", chapter_text)

# 3. 创建角色对象
char_id = "char_xiaoming"
char_data = {
    "名称": "小明",
    "类型": "角色",
    "描述": "穿着蓝色卫衣的年轻男子",
    "所在章节列表": ["chapter_1"]
}
save_object(project, char_id, char_data)

# 4. 创建第一个镜头
shot_1_info = {
    "text": "小明站在路灯下",
    "prompt": "A young man in blue hoodie standing under street light, night, cinematic lighting",
    "script": "（独白）今晚的风好冷。"
}
save_shot(project, 1, shot_1_info)

# 5. 假设我们生成了图片 (这里用假数据模拟)
fake_image_bytes = b'\xFF\xD8\xFF...' 
save_shot_image(project, 1, fake_image_bytes)

# 6. 读取刚刚保存的镜头信息
print(read_shot_info(project, 1))
```