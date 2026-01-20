import os,subprocess,glob
from .processor import ROOT_DIR,analyze_text_to_shots,generate_all
from file_of_film_project import get_list_shots,get_shot_path,read_shot_info


import os
import subprocess
import glob

def generate_video(project_name, force=False, resume=True):
    """
    生成最终视频文件，支持断点续传。
    
    Args:
        project_name: 项目名称
        force: 是否强制重新生成所有片段
        resume: 是否启用断点续传（默认True）
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
    
    # 清空文件列表，重新生成
    if os.path.exists(file_list_path):
        os.remove(file_list_path)
    
    # 统计信息
    total_shots = len(shot_ids)
    processed_shots = 0
    skipped_shots = 0
    failed_shots = 0
    successful_shots = 0
    
    # 断点续传：检查已存在的片段
    existing_segments = {}
    if resume and not force:
        for shot_id in shot_ids:
            segment_path = os.path.join(temp_dir, f"segment_{shot_id}.mp4")
            if os.path.exists(segment_path):
                # 验证片段是否完整
                try:
                    probe_cmd = ["ffprobe", "-v", "error", 
                                 "-show_entries", "format=duration", 
                                 "-of", "default=noprint_wrappers=1:nokey=1", 
                                 segment_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        duration = float(result.stdout.strip())
                        existing_segments[shot_id] = {
                            'path': segment_path,
                            'duration': duration,
                            'valid': True
                        }
                        #print(f"📁 片段 {shot_id}: 发现已生成的有效片段 ({duration:.2f}s)")
                    else:
                        print(f"⚠️ 片段 {shot_id}: 已存在但可能损坏，将重新生成")
                        os.remove(segment_path)
                except:
                    print(f"⚠️ 片段 {shot_id}: 无法验证已存在片段，将重新生成")
                    if os.path.exists(segment_path):
                        os.remove(segment_path)
    
    print(f"\n🎬 开始生成视频项目: {project_name}")
    print(f"📊 总镜头数: {total_shots}")
    print(f"📁 已存在有效片段: {len(existing_segments)}")
    print("─" * 60)
    
    with open(file_list_path, 'w', encoding='utf-8') as f_list:
        total_duration = 0
        
        for idx, shot_id in enumerate(shot_ids, 1):
            processed_shots += 1
            shot_dir = get_shot_path(project_name, shot_id)
            
            img_path = os.path.join(shot_dir, "图片.jpg")
            audio_path = os.path.join(shot_dir, "语音.mp3")
            segment_path = os.path.join(temp_dir, f"segment_{shot_id}.mp4")
            
            shot_info = read_shot_info(project_name, shot_id)
            default_duration = float(shot_info.get("duration", 3.0))
            subtitle_text = shot_info.get("script", "")
            
            # 获取导演指定的时长
            director_duration = float(shot_info.get("时长", 0))
            
            # 断点续传：如果片段已存在且有效，直接使用
            if shot_id in existing_segments and existing_segments[shot_id]['valid'] and not force:
                # 验证文件仍然存在
                if os.path.exists(segment_path):
                    try:
                        # 获取片段时长
                        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                                     "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                                     segment_path]
                        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            actual_duration = float(result.stdout.strip())
                            
                            # 写入文件列表
                            rel_path = os.path.basename(segment_path)
                            f_list.write(f"file '{rel_path}'\n")
                            
                            total_duration += actual_duration
                            successful_shots += 1
                            skipped_shots += 1
                            
                            # 每10个成功片段输出一次进度
                            if successful_shots % 10 == 0:
                                print(f"✅ 进度: 已成功处理 {successful_shots}/{total_shots} 个片段")
                            
                            continue
                    except Exception as e:
                        print(f"⚠️ 片段 {shot_id}: 验证已存在片段时出错: {str(e)[:100]}")
                        # 继续生成新的片段
            
            # ========== 文件有效性检查 ==========
            img_valid = False
            img_error = None
            
            if os.path.exists(img_path):
                try:
                    check_cmd = ["ffprobe", "-v", "error", "-i", img_path]
                    result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        img_valid = True
                    else:
                        img_error = f"ffprobe返回错误: {result.stderr[:200]}"
                except subprocess.TimeoutExpired:
                    img_error = "检查图片文件超时"
                except Exception as e:
                    img_error = f"检查异常: {str(e)[:100]}"
            else:
                img_error = "图片文件不存在"
            
            if not img_valid:
                print(f"❌ 片段 {shot_id}: 图片文件无效 - {img_error}")
                img_path = generate_black_image(temp_dir, shot_id)
                img_valid = True
                print(f"  已生成黑屏图片替代")
            
            # 检查音频文件
            audio_valid = False
            audio_duration = 0
            audio_error = None
            
            if os.path.exists(audio_path):
                try:
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
                        else:
                            audio_error = "音频文件返回空时长"
                    else:
                        audio_error = f"ffprobe返回错误: {result.stderr[:200]}"
                except subprocess.TimeoutExpired:
                    audio_error = "检查音频文件超时"
                except Exception as e:
                    audio_error = f"检查异常: {str(e)[:100]}"
            
            if not audio_valid and audio_error:
                print(f"⚠️ 片段 {shot_id}: 音频文件无效 - {audio_error}")
                print(f"  将使用静音替代")
            
            # ========== 计算实际视频时长 ==========
            actual_duration = default_duration
            
            if audio_valid and audio_duration > 0:
                actual_duration = max(audio_duration, default_duration)
            elif not audio_valid and os.path.exists(audio_path):
                actual_duration = default_duration
            
            if director_duration > 0:
                actual_duration = max(actual_duration, director_duration)
            
            if director_duration > 0:
                total_duration = max(total_duration, director_duration)
            
            # ========== 生成基础视频 ==========
            base_video_path = os.path.join(temp_dir, f"base_{shot_id}.mp4")
            
            if os.path.exists(base_video_path):
                try:
                    os.remove(base_video_path)
                except:
                    pass
            
            # 构建基础视频命令
            if audio_valid and os.path.exists(audio_path):
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
                #print(f"生成基础视频片段 {shot_id}...", end="")
                result = subprocess.run(cmd_base, check=True, 
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       timeout=30)
                #print(" ✅")
                base_success = True
                
                # 验证基础视频
                try:
                    probe_cmd = ["ffprobe", "-v", "error", 
                                 "-show_entries", "format=duration,size",
                                 "-of", "default=noprint_wrappers=1:nokey=1", 
                                 base_video_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        output = result.stdout.strip().split('\n')
                        if len(output) >= 2:
                            base_duration = float(output[0]) if output[0] else 0
                            base_size = int(output[1]) if len(output) > 1 and output[1] else 0
                            #print(f"  基础视频验证: {base_duration:.2f}s, {base_size/1024:.1f}KB")
                            if base_size < 1024:  # 小于1KB可能有问题
                                print(f"  ⚠️ 基础视频文件过小，可能有问题")
                    else:
                        print(f"  ⚠️ 基础视频验证失败")
                except Exception as e:
                    print(f"  ⚠️ 基础视频验证异常: {str(e)[:100]}")
                    
            except subprocess.CalledProcessError as e:
                print(" ❌")
                print(f"❌ 片段 {shot_id}: 基础视频生成失败")
                print(f"   命令: {' '.join(cmd_base)}")
                print(f"   错误输出:")
                error_output = e.stderr.decode('utf-8', errors='ignore')
                for line in error_output.split('\n')[-10:]:
                    if line.strip() and not line.startswith("ffmpeg version"):
                        print(f"     {line}")
                print(f"   退出码: {e.returncode}")
                failed_shots += 1
                continue
            except subprocess.TimeoutExpired:
                print(" ❌")
                print(f"❌ 片段 {shot_id}: 基础视频生成超时")
                failed_shots += 1
                continue
            except Exception as e:
                print(" ❌")
                print(f"❌ 片段 {shot_id}: 基础视频生成异常 - {str(e)}")
                failed_shots += 1
                continue
            
            # ========== 添加字幕 ==========
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
                
                # 构建多行字幕 - 修正：使用与之前版本相同的逻辑
                try:
                    if len(subtitle_lines) == 1:
                        drawtext_filter = f"drawtext=text='{subtitle_text}':fontcolor=white:fontsize=24:fontfile='C\\:/Windows/Fonts/simhei.ttf':x=(w-text_w)/2:y=h-h/8:box=1:boxcolor=black@0.5:boxborderw=5"
                    else:
                        drawtext_parts = []
                        line_height = 30
                        base_y = 576 - (len(subtitle_lines) * line_height)
                        
                        for i, line in enumerate(subtitle_lines):
                            y_position = base_y + (i * line_height)
                            # 转义单引号
                            line_escaped = line.replace("'", "'\\\\\\''")
                            part = f"drawtext=text='{line_escaped}':fontcolor=white:fontsize=24:fontfile='C\\:/Windows/Fonts/simhei.ttf':x=(w-text_w)/2:y={y_position}:box=1:boxcolor=black@0.5:boxborderw=5"
                            drawtext_parts.append(part)
                        
                        drawtext_filter = ",".join(drawtext_parts)
                except Exception as e:
                    print(f"  ⚠️ 字幕滤镜构建失败: {str(e)[:100]}")
                    # 使用简单的字幕
                    drawtext_filter = f"drawtext=text='{subtitle_text[:30]}...':fontcolor=white:fontsize=24:fontfile='C\\:/Windows/Fonts/simhei.ttf':x=(w-text_w)/2:y=h-h/8:box=1:boxcolor=black@0.5:boxborderw=5"
                
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
                    #print(f"为片段 {shot_id} 添加字幕...", end="")
                    result = subprocess.run(cmd_subtitle, check=True,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          timeout=30)
                    #print(" ✅")
                    subtitle_success = True
                except subprocess.CalledProcessError as e:
                    print(" ❌")
                    print(f"❌ 片段 {shot_id}: 字幕添加失败 (drawtext)")
                    error_output = e.stderr.decode('utf-8', errors='ignore')
                    print(f"   错误输出 (前5行):")
                    lines = error_output.split('\n')
                    for i, line in enumerate(lines[:5]):
                        if line.strip():
                            print(f"     {line}")
                    
                    # 尝试使用subtitles滤镜
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
                        result = subprocess.run(cmd_subtitle, check=True,
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE,
                                              timeout=30)
                        print(f"✅ 片段 {shot_id}: 使用subtitle滤镜成功")
                        subtitle_success = True
                    except subprocess.CalledProcessError as e2:
                        print(f"❌ 片段 {shot_id}: 所有字幕方案失败")
                        error_output2 = e2.stderr.decode('utf-8', errors='ignore')
                        print(f"   错误输出 (前3行):")
                        lines2 = error_output2.split('\n')
                        for i, line in enumerate(lines2[:3]):
                            if line.strip():
                                print(f"     {line}")
                        # 使用无字幕版本
                        try:
                            import shutil
                            shutil.copy2(base_video_path, segment_path)
                            print(f"✅ 片段 {shot_id}: 使用无字幕版本")
                            subtitle_success = True
                        except Exception as e3:
                            print(f"❌ 片段 {shot_id}: 复制失败 - {str(e3)}")
                            failed_shots += 1
                            continue
                except subprocess.TimeoutExpired:
                    print(" ❌")
                    print(f"❌ 片段 {shot_id}: 字幕添加超时")
                    failed_shots += 1
                    continue
                except Exception as e:
                    print(" ❌")
                    print(f"❌ 片段 {shot_id}: 字幕添加异常 - {str(e)}")
                    failed_shots += 1
                    continue
            elif base_success:
                # 没有字幕，直接复制基础视频
                try:
                    import shutil
                    shutil.copy2(base_video_path, segment_path)
                    subtitle_success = True
                except Exception as e:
                    print(f"❌ 片段 {shot_id}: 复制基础视频失败 - {str(e)}")
                    failed_shots += 1
                    continue
            
            # 清理基础视频文件
            if os.path.exists(base_video_path):
                try:
                    os.remove(base_video_path)
                except:
                    pass
            
            # ========== 验证生成的片段 ==========
            if os.path.exists(segment_path) and subtitle_success:
                try:
                    # 修复：使用正确的ffprobe命令格式
                    probe_cmd = ["ffprobe", "-v", "error", 
                                 "-show_entries", "format=duration,size",
                                 "-of", "default=noprint_wrappers=1:nokey=1", 
                                 segment_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        output_lines = result.stdout.strip().split('\n')
                        if len(output_lines) >= 2 and output_lines[0]:
                            actual_segment_duration = float(output_lines[0])
                            file_size = int(output_lines[1]) if len(output_lines) > 1 and output_lines[1] else 0
                            
                            # 写入文件列表
                            rel_path = os.path.basename(segment_path)
                            f_list.write(f"file '{rel_path}'\n")
                            
                            total_duration += actual_segment_duration
                            successful_shots += 1
                            
                            # 每10个成功片段输出一次进度
                            if successful_shots % 10 == 0:
                                print(f"\n✅ 进度报告: 已成功处理 {successful_shots}/{total_shots} 个片段")
                                print(f"   当前片段: {shot_id}, 时长: {actual_segment_duration:.2f}秒, 大小: {file_size/1024:.1f}KB")
                                print("   " + "=" * 40)
                            else:
                                pass
                                #print(f"✅ 片段 {shot_id} 完成: {actual_segment_duration:.2f}s, {file_size/1024:.1f}KB")
                        else:
                            print(f"❌ 片段 {shot_id}: ffprobe返回无效输出: {result.stdout}")
                            failed_shots += 1
                    else:
                        print(f"❌ 片段 {shot_id}: ffprobe命令失败")
                        print(f"   错误: {result.stderr[:200]}")
                        failed_shots += 1
                        
                except ValueError as e:
                    print(f"❌ 片段 {shot_id}: 解析ffprobe输出失败 - {str(e)}")
                    print(f"   ffprobe输出: {result.stdout if 'result' in locals() else '无输出'}")
                    failed_shots += 1
                except Exception as e:
                    print(f"❌ 片段 {shot_id}: 无法验证片段时长 - {str(e)}")
                    if os.path.exists(segment_path):
                        try:
                            file_size = os.path.getsize(segment_path)
                            print(f"   文件大小: {file_size} 字节")
                            if file_size < 1024:
                                print(f"   ⚠️ 文件过小，可能生成失败")
                                os.remove(segment_path)
                        except:
                            pass
                    failed_shots += 1
            else:
                print(f"❌ 片段 {shot_id}: 片段未生成")
                failed_shots += 1
    
    # ========== 输出最终统计信息 ==========
    print(f"\n" + "=" * 60)
    print(f"🎬 片段生成完成")
    print(f"  总镜头数: {total_shots}")
    print(f"  成功处理: {successful_shots}")
    print(f"  跳过(已存在): {skipped_shots}")
    print(f"  失败: {failed_shots}")
    print(f"  预计总时长: {total_duration:.2f}秒 ({total_duration/60:.1f}分钟)")
    print("=" * 60)
    
    if successful_shots == 0:
        print("❌ 没有成功生成任何视频片段，无法合并")
        return None
    
    # 检查文件列表
    if not os.path.exists(file_list_path) or os.path.getsize(file_list_path) == 0:
        print("❌ 文件列表为空，无法合并")
        return None
    
    # 读取文件列表内容
    with open(file_list_path, 'r', encoding='utf-8') as f:
        files = f.read().strip().split('\n')
        print(f"📋 将合并 {len(files)} 个视频片段")
    
    print(f"\n🔗 开始合并视频片段...")
    
    # ========== 合并视频片段 ==========
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", file_list_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    merge_success = False
    try:
        print("尝试直接合并...", end="")
        result = subprocess.run(concat_cmd, check=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               timeout=120)
        print(" ✅")
        merge_success = True
    except subprocess.CalledProcessError as e:
        print(" ❌")
        print(f"❌ 直接合并失败")
        print(f"   命令: {' '.join(concat_cmd)}")
        error_output = e.stderr.decode('utf-8', errors='ignore')
        print(f"   错误输出 (关键部分):")
        lines = error_output.split('\n')
        error_found = False
        for line in lines:
            if line.strip() and ("error" in line.lower() or "failed" in line.lower() or "invalid" in line.lower()):
                print(f"     {line}")
                error_found = True
        if not error_found:
            for line in lines[-10:]:
                if line.strip():
                    print(f"     {line}")
        
        print(f"   退出码: {e.returncode}")
        print("尝试重新编码合并...")
        
        # 重新编码合并
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
            result = subprocess.run(concat_cmd, check=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  timeout=180)
            print("重新编码合并成功 ✅")
            merge_success = True
        except subprocess.CalledProcessError as e2:
            print(f"❌ 重新编码合并也失败")
            error_output2 = e2.stderr.decode('utf-8', errors='ignore')
            print(f"   关键错误:")
            lines2 = error_output2.split('\n')
            for line in lines2:
                if line.strip() and ("error" in line.lower() or "failed" in line.lower()):
                    print(f"     {line}")
            return None
        except subprocess.TimeoutExpired:
            print(f"❌ 重新编码合并超时")
            return None
    except subprocess.TimeoutExpired:
        print(" ❌")
        print(f"❌ 合并超时")
        return None
    
    # ========== 验证最终视频 ==========
    if merge_success and os.path.exists(output_path):
        try:
            probe_cmd = ["ffprobe", "-v", "error", 
                         "-show_entries", "format=duration,size,bit_rate", 
                         "-of", "default=noprint_wrappers=1:nokey=1", 
                         output_path]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            info = result.stdout.strip().split('\n')
            
            if len(info) >= 3:
                final_duration = float(info[0])
                file_size = int(info[1]) / (1024 * 1024)  # MB
                bitrate = int(info[2]) / 1000 if info[2] else 0  # kbps
                
                print(f"\n" + "=" * 60)
                print(f"🎉 视频生成成功!")
                print(f"  📍 文件路径: {output_path}")
                print(f"  ⏱️ 总时长: {final_duration:.2f}秒 ({final_duration/60:.1f}分钟)")
                print(f"  📦 文件大小: {file_size:.2f} MB")
                if bitrate > 0:
                    print(f"  📡 比特率: {bitrate:.0f} kbps")
                print(f"  🎞️ 合并片段数: {successful_shots}个")
                print(f"  ⚡ 生成状态: {'全新生成' if force else ('断点续传' if skipped_shots > 0 else '完整生成')}")
                print("=" * 60)
            else:
                print(f"✅ 视频已生成，但无法获取详细信息: {output_path}")
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
            # 备用方案
            try:
                from PIL import Image
                img = Image.new('RGB', (1024, 576), color='black')
                img.save(img_path, 'JPEG')
            except:
                with open(img_path, 'wb') as f:
                    f.write(b'')
    return img_path