from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS
import time
import hashlib
import os
import random
import string

# 导入你的模块
from modules.processor import *
from modules.generate_video import generate_video

app = Flask(__name__)
CORS(app)

# 固定项目名
PROJECT_NAME = 'test'

def generate_random_seed():
    """生成一个看起来像的随机种子"""
    return ''.join(random.choices(string.hexdigits, k=16))

@app.route('/api/generate/images', methods=['POST'])
def generate_images():
    """
    生成图片的端点
    请求体: {"prompt": "文本描述", "count": 4}
    返回: GeneratedImage[] 列表
    """
    try:
        # 获取前端数据
        data = request.get_json()
        text = data.get('prompt', '')
        
        if not text:
            return jsonify({'error': '请输入文本描述'}), 400
        
        # 调用后端逻辑（生成图片和视频）
        if not get_chapter_list(PROJECT_NAME) and False:  # 改为 or False
            delete_project_folder(PROJECT_NAME)
            create_project_folder(PROJECT_NAME)
            save_raw_text(PROJECT_NAME, text)
            analyze_text_to_shots(PROJECT_NAME)
            generate_all(PROJECT_NAME)
            generate_video(PROJECT_NAME, force=False)
        
        # 获取所有镜头ID
        shot_ids = get_list_shots(PROJECT_NAME)
        
        # 构建返回数据
        images = []
        current_time = int(time.time() * 1000)
        
        for shot_id in shot_ids:
            # 获取图片绝对路径（使用正确的方式）
            shot_dir = get_shot_path(PROJECT_NAME, shot_id)
            if shot_dir:
                img_path = os.path.join(shot_dir, "图片.jpg")
                
                # 检查图片是否存在
                if os.path.exists(img_path):
                    # 构建图片信息
                    image_info = {
                        'id': shot_id,
                        'url': f'/api/images/{shot_id}',  # 使用shot_id作为URL参数
                        'prompt': text,  # 使用前端传来的文本
                        'seed': generate_random_seed(),  # 随机种子
                        'createdAt': current_time
                    }
                    images.append(image_info)
        
        return jsonify(images)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate/video', methods=['POST'])
def generate_video_endpoint():
    """
    获取视频信息的端点
    请求体: {"images": [...]}（直接忽略）
    返回: GeneratedVideo
    """
    try:
        # 获取视频路径
        project_folder = get_project_folder(PROJECT_NAME)
        video_path = os.path.join(project_folder, "final_movie.mp4")
        
        # 检查视频是否存在，如果不存在则生成
        if not os.path.exists(video_path):
            generate_video(PROJECT_NAME, force=False)
        
        # 构建返回数据
        video_info = {
            'id': f'video_{PROJECT_NAME}',
            'url': '/api/video',  # 视频访问URL
            'createdAt': int(time.time() * 1000)
        }
        
        return jsonify(video_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/images/<shot_id>')
def get_image(shot_id):
    """
    获取图片文件的端点
    参数: shot_id - 镜头ID
    返回: 图片二进制数据
    """
    try:
        # 使用正确的方式获取图片路径
        shot_dir = get_shot_path(PROJECT_NAME, shot_id)
        if shot_dir:
            img_path = os.path.join(shot_dir, "图片.jpg")
            
            # 检查文件是否存在
            if os.path.exists(img_path):
                return send_file(img_path, mimetype='image/jpeg')
        
        # 如果图片不存在，返回空响应
        return Response(status=204)  # No Content
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/video')
def get_video():
    """
    获取视频文件的端点
    返回: 视频二进制数据
    """
    try:
        # 获取视频路径
        project_folder = get_project_folder(PROJECT_NAME)
        video_path = os.path.join(project_folder, "final_movie.mp4")
        
        # 检查视频是否存在
        if os.path.exists(video_path):
            return send_file(video_path, mimetype='video/mp4')
        
        # 如果视频不存在，返回空响应
        return Response(status=204)  # No Content
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'healthy', 'project': PROJECT_NAME})

if __name__ == '__main__':
    # 启动Flask应用
    print("启动Flask API服务器...")
    print(f"项目名称: {PROJECT_NAME}")
    print("API端点:")
    print("  POST /api/generate/images - 生成图片")
    print("  POST /api/generate/video - 获取视频信息")
    print("  GET  /api/images/<shot_id> - 获取图片文件")
    print("  GET  /api/video - 获取视频文件")
    print("  GET  /api/health - 健康检查")
    print("\n服务器将在 http://localhost:5000 启动")
    
    app.run(debug=True, host='0.0.0.0', port=5000)