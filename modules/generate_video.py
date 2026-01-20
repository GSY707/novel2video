import os,subprocess,glob
from .processor import ROOT_DIR,analyze_text_to_shots,generate_all
from file_of_film_project import get_list_shots,get_shot_path,read_shot_info


import os
import subprocess
import glob

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
    for pattern in ["segment_*.mp4", "base_*.mp4", "sub_*.srt", "black_*.jpg"]:
        for f in glob.glob(os.path.join(temp_dir, pattern)):
            try:
                os.remove(f)
            except:
                pass
    
    with open(file_list_path, 'w', encoding='utf-8') as f_list:
        total_duration = 0
        successful_segments = 0
        failed_segments = 0
        
        for shot_id in shot_ids:
            shot_dir = get_shot_path(project_name, shot_id)
            
            img_path = os.path.join(shot_dir, "图片.jpg")
            audio_path = os.path.join(shot_dir, "语音.mp3")
            segment_path = os.path.join(temp_dir, f"segment_{shot_id}.mp4")
            
            shot_info = read_shot_info(project_name, shot_id)
            default_duration = float(shot_info.get("duration", 3.0))
            subtitle_text = shot_info.get("script", "")
            
            # 获取导演指定的时长
            director_duration = float(shot_info.get("时长", 3))
            
            # 1. 检查图片文件
            img_valid = False
            if os.path.exists(img_path):
                try:
                    # 尝试检查图片文件是否有效
                    check_cmd = ["ffprobe", "-v", "error", "-i", img_path]
                    result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        img_valid = True
                        print(f"✅ 片段 {shot_id}: 图片文件有效")
                    else:
                        print(f"❌ 片段 {shot_id}: 图片文件损坏或无法读取，将使用黑屏替代")
                except subprocess.TimeoutExpired:
                    print(f"❌ 片段 {shot_id}: 图片文件检查超时，可能已损坏，将使用黑屏替代")
                except Exception as e:
                    print(f"❌ 片段 {shot_id}: 图片文件检查失败: {str(e)[:100]}...，将使用黑屏替代")
            else:
                print(f"❌ 片段 {shot_id}: 图片文件不存在，将使用黑屏替代")
                break
            
            # 如果图片无效，生成黑屏
            if not img_valid:
                img_path = generate_black_image(temp_dir, shot_id)
                img_valid = True  # 黑屏图片应该总是有效的
            
            # 2. 检查音频文件
            audio_valid = False
            audio_duration = 0
            if os.path.exists(audio_path):
                try:
                    # 获取音频时长并检查文件有效性
                    audio_duration_cmd = ["ffprobe", "-v", "error", 
                                         "-show_entries", "format=duration", 
                                         "-of", "default=noprint_wrappers=1:nokey=1", 
                                         audio_path]
                    result = subprocess.run(audio_duration_cmd, capture_output=True, text=True, encoding='utf-8', timeout=5)
                    
                    if result.returncode == 0:
                        duration_str = result.stdout.strip()
                        if duration_str and duration_str != '':
                            audio_duration = float(duration_str)
                            audio_valid = True
                            print(f"✅ 片段 {shot_id}: 音频文件有效，时长={audio_duration:.2f}s")
                        else:
                            print(f"❌ 片段 {shot_id}: 音频文件返回空时长，可能已损坏，将忽略音频")
                    else:
                        print(f"❌ 片段 {shot_id}: 音频文件检查失败，可能已损坏，将忽略音频")
                except subprocess.TimeoutExpired:
                    print(f"❌ 片段 {shot_id}: 音频文件检查超时，可能已损坏，将忽略音频")
                except Exception as e:
                    print(f"❌ 片段 {shot_id}: 音频文件检查异常: {str(e)[:100]}...，将忽略音频")
            else:
                print(f"⚠️ 片段 {shot_id}: 无音频文件")
            
            # 3. 计算实际视频时长
            actual_duration = default_duration
            
            if audio_valid and audio_duration > 0:
                # 取音频时长和默认时长的最大值
                actual_duration = max(audio_duration, default_duration)
            elif not audio_valid and os.path.exists(audio_path):
                # 音频文件存在但损坏，使用默认时长
                print(f"⚠️ 片段 {shot_id}: 音频文件损坏，使用默认时长 {default_duration}s")
                actual_duration = default_duration
            else:
                # 无音频文件或音频文件不存在
                actual_duration = default_duration
            
            # 如果有导演指定的时长，取最大值
            if director_duration > 0:
                actual_duration = max(actual_duration, director_duration)
                print(f"✅ 片段 {shot_id}: 导演指定时长={director_duration}s，最终使用={actual_duration:.2f}s")
            
            # 更新总时长：取累积时长和导演时长的最大值
            if director_duration > 0:
                total_duration = max(total_duration, director_duration)
            
            # 4. 生成基础视频（无字幕）
            base_video_path = os.path.join(temp_dir, f"base_{shot_id}.mp4")
            
            # 构建基础视频命令
            cmd_base = []
            if audio_valid and os.path.exists(audio_path):
                # 有有效音频的情况
                cmd_base = [
                    "ffmpeg", "-y",
                    "-loop", "1", 
                    "-i", img_path,
                    "-i", audio_path,
                    "-t", str(actual_duration),
                    "-c:v", "libx264", 
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-r", "25",
                    "-vf", "scale=1024:576",
                    "-c:a", "aac", 
                    "-b:a", "128k", 
                    "-ar", "44100",
                    "-shortest",
                    base_video_path
                ]
            else:
                # 没有音频或音频无效的情况，使用静音
                cmd_base = [
                    "ffmpeg", "-y",
                    "-loop", "1", 
                    "-i", img_path,
                    "-f", "lavfi", 
                    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t", str(actual_duration),
                    "-c:v", "libx264", 
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-r", "25",
                    "-vf", "scale=1024:576",
                    "-c:a", "aac", 
                    "-b:a", "64k", 
                    "-ar", "44100",
                    "-shortest",
                    base_video_path
                ]
            
            # 生成基础视频
            base_success = False
            try:
                print(f"生成基础视频片段 {shot_id} (时长: {actual_duration:.2f}秒)...", end="")
                result = subprocess.run(cmd_base, check=True, 
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       timeout=30)
                print(" ✅")
                base_success = True
            except subprocess.CalledProcessError as e:
                print(" ❌")
                print(f"  基础视频生成失败:")
                print(f"  命令: {' '.join(cmd_base[:10])}...")  # 只显示命令前10个参数
                error_msg = e.stderr.decode('utf-8', errors='ignore')
                if "Invalid data found when processing input" in error_msg:
                    print(f"  错误: 输入文件无效，可能已损坏")
                elif "No such file or directory" in error_msg:
                    print(f"  错误: 文件不存在")
                else:
                    # 提取关键错误信息
                    lines = error_msg.split('\n')
                    for line in lines[-5:]:  # 显示最后5行错误信息
                        if line.strip() and not line.startswith("ffmpeg version"):
                            print(f"  错误: {line[:200]}")
                
                print(f"  尝试备用方案...")
                
                # 尝试更简单的方法
                try:
                    if audio_valid and os.path.exists(audio_path):
                        cmd_simple = [
                            "ffmpeg", "-y",
                            "-loop", "1", 
                            "-i", img_path,
                            "-i", audio_path,
                            "-c:v", "libx264", 
                            "-pix_fmt", "yuv420p",
                            "-vf", "scale=1024:576",
                            "-c:a", "aac",
                            "-shortest",
                            base_video_path
                        ]
                    else:
                        cmd_simple = [
                            "ffmpeg", "-y",
                            "-loop", "1", 
                            "-i", img_path,
                            "-t", str(actual_duration),
                            "-c:v", "libx264", 
                            "-pix_fmt", "yuv420p",
                            "-vf", "scale=1024:576",
                            base_video_path
                        ]
                    
                    subprocess.run(cmd_simple, check=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  timeout=30)
                    print(f"  备用方案成功 ✅")
                    base_success = True
                except subprocess.CalledProcessError as e2:
                    print(f"  备用方案失败 ❌")
                    error_msg2 = e2.stderr.decode('utf-8', errors='ignore')
                    if "Invalid data found when processing input" in error_msg2:
                        print(f"  错误: 输入文件无效，可能已损坏")
                    failed_segments += 1
                    continue
                except subprocess.TimeoutExpired:
                    print(f"  备用方案超时 ❌")
                    failed_segments += 1
                    continue
            except subprocess.TimeoutExpired:
                print(" ❌")
                print(f"  生成超时，可能文件过大或已损坏")
                failed_segments += 1
                continue
            
            # 5. 如果有字幕，添加字幕
            subtitle_success = False
            if subtitle_text and subtitle_text.strip() and base_success:
                subtitle_path = os.path.join(temp_dir, f"sub_{shot_id}.srt")
                
                # 生成SRT字幕文件
                with open(subtitle_path, 'w', encoding='utf-8') as f_srt:
                    start_time = "00:00:00,000"
                    end_time_seconds = int(actual_duration)
                    end_time_ms = int((actual_duration - end_time_seconds) * 1000)
                    end_time = f"00:{end_time_seconds:02d}:{end_time_ms:03d},000"
                    
                    f_srt.write(f"1\n{start_time} --> {end_time}\n{subtitle_text}\n")
                
                # 智能换行处理
                max_chars_per_line = 30
                subtitle_lines = []
                
                if '\n' in subtitle_text:
                    subtitle_lines = subtitle_text.split('\n')
                else:
                    current_line = ""
                    for char in subtitle_text:
                        if len(current_line) >= max_chars_per_line:
                            subtitle_lines.append(current_line)
                            current_line = char
                        else:
                            current_line += char
                    if current_line:
                        subtitle_lines.append(current_line)
                
                # 构建多行字幕
                if len(subtitle_lines) == 1:
                    drawtext_filter = f"drawtext=text='{subtitle_text}':fontcolor=white:fontsize=24:fontfile='C\\:/Windows/Fonts/simhei.ttf':x=(w-text_w)/2:y=h-h/8:box=1:boxcolor=black@0.5:boxborderw=5"
                else:
                    drawtext_parts = []
                    line_height = 30
                    base_y = 576 - (len(subtitle_lines) * line_height)
                    
                    for i, line in enumerate(subtitle_lines):
                        y_position = base_y + (i * line_height)
                        part = f"drawtext=text='{line}':fontcolor=white:fontsize=24:fontfile='C\\:/Windows/Fonts/simhei.ttf':x=(w-text_w)/2:y={y_position}:box=1:boxcolor=black@0.5:boxborderw=5"
                        drawtext_parts.append(part)
                    
                    drawtext_filter = ",".join(drawtext_parts)
                
                # 处理Windows路径问题
                subtitle_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:')
                
                # 首选使用drawtext滤镜
                cmd_subtitle = [
                    "ffmpeg", "-y",
                    "-i", base_video_path,
                    "-vf", drawtext_filter,
                    "-c:v", "libx264",
                    "-c:a", "copy",
                    "-preset", "fast",
                    segment_path
                ]
                
                # 添加字幕
                try:
                    print(f"为片段 {shot_id} 添加字幕...", end="")
                    subprocess.run(cmd_subtitle, check=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  timeout=30)
                    print(" ✅")
                    subtitle_success = True
                except subprocess.CalledProcessError as e:
                    print(" ❌")
                    print(f"  字幕添加失败，尝试备用方案...")
                    
                    try:
                        subtitle_args = f"subtitles='{subtitle_path_escaped}':force_style='FontName=SimHei,FontSize=24,Alignment=2,MarginV=30,WrapStyle=1'"
                        cmd_subtitle = [
                            "ffmpeg", "-y",
                            "-i", base_video_path,
                            "-vf", subtitle_args,
                            "-c:v", "libx264",
                            "-c:a", "copy",
                            "-preset", "fast",
                            segment_path
                        ]
                        subprocess.run(cmd_subtitle, check=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      timeout=30)
                        print(f"  备用方案成功 ✅")
                        subtitle_success = True
                    except subprocess.CalledProcessError as e2:
                        print(f"  所有字幕方案失败 ❌")
                        # 复制基础视频作为最终片段
                        try:
                            import shutil
                            shutil.copy2(base_video_path, segment_path)
                            print(f"  使用无字幕版本 ✅")
                            subtitle_success = True
                        except Exception as e3:
                            print(f"  复制失败: {str(e3)[:100]}")
                            failed_segments += 1
                            continue
                except subprocess.TimeoutExpired:
                    print(" ❌")
                    print(f"  字幕添加超时")
                    failed_segments += 1
                    continue
            elif base_success:
                # 没有字幕，直接复制基础视频
                try:
                    import shutil
                    shutil.copy2(base_video_path, segment_path)
                    subtitle_success = True
                except Exception as e:
                    print(f"⚠️ 片段 {shot_id}: 复制基础视频失败: {str(e)[:100]}")
                    failed_segments += 1
                    continue
            
            # 清理基础视频文件
            if os.path.exists(base_video_path):
                try:
                    os.remove(base_video_path)
                except:
                    pass
            
            # 验证生成的片段
            if os.path.exists(segment_path) and subtitle_success:
                try:
                    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                                segment_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    actual_segment_duration = float(result.stdout.strip())
                    
                    # 写入文件列表
                    rel_path = os.path.basename(segment_path)
                    f_list.write(f"file '{rel_path}'\n")
                    
                    successful_segments += 1
                    print(f"✅ 片段 {shot_id} 完成，时长: {actual_segment_duration:.2f}秒")
                except Exception as e:
                    print(f"❌ 片段 {shot_id}: 无法验证片段时长: {str(e)[:100]}")
                    failed_segments += 1
            else:
                print(f"❌ 片段 {shot_id}: 片段未生成")
                failed_segments += 1
    
    # 输出统计信息
    print(f"\n📊 生成统计:")
    print(f"  成功片段: {successful_segments}/{len(shot_ids)}")
    print(f"  失败片段: {failed_segments}/{len(shot_ids)}")
    
    if successful_segments == 0:
        print("❌ 没有成功生成任何视频片段，无法合并")
        return None
    
    # 检查文件列表
    if not os.path.exists(file_list_path) or os.path.getsize(file_list_path) == 0:
        print("❌ 文件列表为空，无法合并")
        return None
    
    # 读取文件列表内容用于调试
    with open(file_list_path, 'r', encoding='utf-8') as f:
        files = f.read().strip().split('\n')
        print(f"📋 将合并 {len(files)} 个视频片段")
    
    print(f"\n🎬 开始合并视频片段...")
    
    # 使用 concat demuxer 合并视频
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", file_list_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    # 首先尝试直接合并
    merge_success = False
    try:
        print("尝试直接合并...", end="")
        subprocess.run(concat_cmd, check=True,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE,
                      timeout=60)
        print(" ✅")
        merge_success = True
    except subprocess.CalledProcessError as e:
        print(" ❌")
        error_msg = e.stderr.decode('utf-8', errors='ignore')
        print(f"  直接合并失败:")
        # 提取关键错误信息
        lines = error_msg.split('\n')
        for line in lines[-5:]:
            if line.strip() and not line.startswith("ffmpeg version"):
                print(f"  错误: {line[:200]}")
        
        print("  尝试重新编码合并...")
        
        # 如果直接合并失败，尝试重新编码
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-movflags", "+faststart",
            output_path
        ]
        try:
            subprocess.run(concat_cmd, check=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          timeout=120)
            print("  重新编码合并成功 ✅")
            merge_success = True
        except subprocess.CalledProcessError as e2:
            print(f"  重新编码合并也失败 ❌")
            error_msg2 = e2.stderr.decode('utf-8', errors='ignore')
            lines = error_msg2.split('\n')
            for line in lines[-5:]:
                if line.strip() and not line.startswith("ffmpeg version"):
                    print(f"  错误: {line[:200]}")
            return None
        except subprocess.TimeoutExpired:
            print(f"  重新编码合并超时 ❌")
            return None
    except subprocess.TimeoutExpired:
        print(" ❌")
        print(f"  合并超时")
        return None
    
    # 验证最终视频
    if merge_success and os.path.exists(output_path):
        try:
            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                        "format=duration,size", "-of", "default=noprint_wrappers=1:nokey=1", 
                        output_path]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            info = result.stdout.strip().split('\n')
            
            if len(info) >= 2:
                final_duration = float(info[0])
                file_size = int(info[1]) / (1024 * 1024)  # MB
                
                print(f"\n✅ 视频生成成功!")
                print(f"  📍 文件路径: {output_path}")
                print(f"  ⏱️ 总时长: {final_duration:.2f}秒 ({final_duration/60:.2f}分钟)")
                print(f"  📦 文件大小: {file_size:.2f} MB")
                print(f"  🎞️ 成功片段数: {successful_segments}个")
            else:
                print(f"✅ 视频已生成: {output_path}")
        except Exception as e:
            print(f"⚠️ 视频已生成但无法验证信息: {str(e)[:100]}")
            print(f"📍 文件路径: {output_path}")
    
    return output_path if merge_success else None


def generate_black_image(temp_dir, shot_id):
    """生成黑色背景图"""
    img_path = os.path.join(temp_dir, f"black_{shot_id}.jpg")
    if not os.path.exists(img_path):
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", 
                "-i", "color=c=black:s=1024x576",
                "-frames:v", "1",
                img_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except:
            # 如果生成失败，创建一个简单的黑色图片文件
            try:
                from PIL import Image
                img = Image.new('RGB', (1024, 576), color='black')
                img.save(img_path, 'JPEG')
            except:
                # 如果PIL也不可用，创建一个小文件占位
                with open(img_path, 'wb') as f:
                    f.write(b'')  # 空文件
    return img_path