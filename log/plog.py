import cv2
import time
import os
import numpy as np
import threading
import global_vars
from queue import Queue
import subprocess
import glob
import shutil

class PictureLogger():
    def __init__(self, config: dict) -> None:
        self.video_path = config["video_path"]
        self.data_queue = config["data_queue"]
        self.image_path = config["image_path"]
        self.image_type = config["image_type"]
        self.lock = threading.Lock()

        self.timestamps = []
        self.frame_count = 0
        
        # 确保目录存在
        os.makedirs(self.image_path, exist_ok=True)
        # 确保视频文件的目录存在
        os.makedirs(os.path.dirname(self.video_path), exist_ok=True)
        
        video_path = os.path.abspath(self.video_path).replace('.mkv', '.avi')
        self.out = None
        with open(f'{video_path}.ts', 'w') as f:
            f.write('frame,ts\n')

    def save_image(self, index: int, image: np.ndarray, timestamp: float) -> None:
        if self.image_type == "np":
            image = image[0]
            # 处理numpy数组格式的图像（原有逻辑）
            if np.max(image)<=1.0:
                image = (image * 255).astype(np.uint8)
            else:
                image = image.astype('uint8')
            if image.ndim == 3 and image.shape[2] == 4:
                image = image[:, :, :3]
        elif self.image_type == "raw":
            image = image[1]
            # 处理cv2.RGB格式的图像，需要转换为BGR格式
            # 确保图像是uint8格式
            if image.dtype != np.uint8:
                if np.max(image)<=1.0:
                    image = (image * 255).astype(np.uint8)
                else:
                    image = image.astype(np.uint8)
            # 如果有alpha通道，移除它
            if image.ndim == 3 and image.shape[2] == 4:
                image = image[:, :, :3]
            # 将RGB转换为BGR格式（cv2默认使用BGR）
            if image.ndim == 3 and image.shape[2] == 3:
                #image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                pass
        else:
            # 默认处理（保持原有逻辑）
            image = image[0]
            if np.max(image)<=1.0:
                image = (image * 255).astype(np.uint8)
            if image.ndim == 3 and image.shape[2] == 4:
                image = image[:, :, :3]
            else:
                image = image.astype('uint8')
        
        self.timestamps.append(timestamp)
        video_path = os.path.abspath(self.video_path).replace('.mkv', '.avi')
        if not self.out:
            fourcc_mjpg = cv2.VideoWriter_fourcc(*'MJPG')
            h, w = image.shape[:2]
            self.out = cv2.VideoWriter(video_path, fourcc_mjpg, 30., (w, h))
        self.out.write(image)
        with open(f'{video_path}.ts', 'a+') as f:
            f.write(f'{self.frame_count},{timestamp}\n')
        
        

    def save_video(self) -> None:
        # 检查是否有帧需要保存
        if self.frame_count == 0:
            print("[PictureLogger] No frames to save, skipping video creation")
            return
        
        # 如果pipeline已经停止并且没有足够的帧，可能跳过视频创建
        if not global_vars.pipeline_running and self.frame_count < 5:
            print(f"[PictureLogger] Too few frames ({self.frame_count}) for video creation, skipping")
            return
            
        txt_path = os.path.join(self.image_path, "timestamps.txt")
        
        # 确保视频输出目录存在
        video_dir = os.path.dirname(self.video_path)
        if video_dir and not os.path.exists(video_dir):
            os.makedirs(video_dir, exist_ok=True)
            print(f"[PictureLogger] Created video directory: {video_dir}")
        
        # 计算平均帧率
        total_duration = 0.0
        frame_durations = []
        
        with open(txt_path, "w") as f:
            for i in range(self.frame_count - 1):
                dt = self.timestamps[i + 1] - self.timestamps[i]
                frame_durations.append(dt)
                total_duration += dt
                f.write(f"file 'frame_{i:06d}.png'\n")
                f.write(f"duration {dt:.6f}\n")
            f.write(f"file 'frame_{self.frame_count - 1:06d}.png'\n")
            f.write(f"duration 0.033\n")

        # 计算并打印帧率统计信息
        if self.frame_count > 1 and total_duration > 0:
            # 方法1: 基于总时长和帧数
            video_duration = self.timestamps[-1] - self.timestamps[0]
            average_fps_total = (self.frame_count - 1) / video_duration if video_duration > 0 else 0
            
            # 方法2: 基于平均帧间隔
            average_frame_interval = total_duration / (self.frame_count - 1) if self.frame_count > 1 else 0
            average_fps_interval = 1.0 / average_frame_interval if average_frame_interval > 0 else 0
            
            # 计算帧率的标准差
            if len(frame_durations) > 1:
                fps_values = [1.0/dt if dt > 0 else 0 for dt in frame_durations]
                mean_fps = sum(fps_values) / len(fps_values)
                variance = sum((fps - mean_fps) ** 2 for fps in fps_values) / len(fps_values)
                std_fps = variance ** 0.5
            else:
                mean_fps = 0
                std_fps = 0
            
            print(f"[PictureLogger] Video statistics:")
            print(f"  - Total frames: {self.frame_count}")
            print(f"  - Video duration: {video_duration:.3f} seconds")
            print(f"  - Average FPS (total): {average_fps_total:.2f}")
            print(f"  - Average FPS (interval): {average_fps_interval:.2f}")
            print(f"  - FPS std deviation: {std_fps:.2f}")
            print(f"  - Min frame interval: {min(frame_durations):.6f}s")
            print(f"  - Max frame interval: {max(frame_durations):.6f}s")
        else:
            print(f"[PictureLogger] Insufficient data to calculate frame rate (frames: {self.frame_count})")

        # 使用绝对路径
        abs_video_path = os.path.abspath(self.video_path)
        
        cmd = [
            "ffmpeg",
            "-fflags", "+genpts",
            "-f", "concat",
            "-safe", "0",
            "-i", "timestamps.txt",
            "-c:v", "ffv1",       # 改成 FFV1 编码
            "-level", "3",        # 使用 FFV1 第三版（更高压缩率和效率）
            "-pix_fmt", "yuv444p",# 无损保色
            "-vsync", "vfr",
            abs_video_path        # 建议扩展名用 .mkv
        ]

        old_cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "timestamps.txt",
            "-vsync", "vfr",
            "-c:v", "mpeg4",
            "-pix_fmt", "yuv420p",
            abs_video_path
        ]

        debug_cmd = [
            "ffmpeg",
            "-framerate", "30",
            "-i", "frame_%06d.png",
            "-c:v", "mpeg4",
            "-pix_fmt", "yuv420p",
            "test.mp4"
        ]

        print(f"[PictureLogger] Attempting to create video at: {abs_video_path}")
        print(f"[PictureLogger] Working directory: {self.image_path}")
        print(f"[PictureLogger] Frame count: {self.frame_count}")

        return
        
        try:
            # 检查 timestamps.txt 文件是否存在
            if not os.path.exists(txt_path):
                print(f"[PictureLogger] Error: timestamps.txt not found at {txt_path}")
                return
                
            # 添加超时以防止FFmpeg挂起
            result = subprocess.run(cmd, cwd=self.image_path, check=True, capture_output=True, text=True, timeout=120)
            print("[PictureLogger] FFmpeg stdout:", result.stdout)
            if result.stderr:
                print("[PictureLogger] FFmpeg stderr:", result.stderr)
                
        except subprocess.CalledProcessError as e:
            print(f"[PictureLogger] Error during ffmpeg execution: {e}")
            print(f"[PictureLogger] Return code: {e.returncode}")
            if e.stdout:
                print(f"[PictureLogger] Command output: {e.stdout}")
            if e.stderr:
                print(f"[PictureLogger] Command error: {e.stderr}")
            
            # 尝试备用方法
            print("[PictureLogger] Trying alternative ffmpeg command...")
            try:
                backup_cmd = [
                    "ffmpeg",
                    "-y",
                    "-framerate", "30",
                    "-i", "frame_%06d.png",
                    "-c:v", "mpeg4",
                    "-pix_fmt", "yuv420p",
                    abs_video_path
                ]
                result = subprocess.run(backup_cmd, cwd=self.image_path, check=True, capture_output=True, text=True, timeout=120)
                print("[PictureLogger] Backup FFmpeg command succeeded")
            except subprocess.CalledProcessError as e2:
                print(f"[PictureLogger] Backup command also failed: {e2}")
                return
            except subprocess.TimeoutExpired:
                print("[PictureLogger] Backup FFmpeg command timed out")
                return
        except subprocess.TimeoutExpired:
            print("[PictureLogger] FFmpeg command timed out")
            return

        time.sleep(5)  # 等待FFmpeg完成写入
        # 清理文件 - 直接删除整个image_path文件夹，然后重新创建
        try:
            # 删除整个image_path文件夹（包含所有文件）
            if os.path.exists(self.image_path):
                shutil.rmtree(self.image_path)
                print(f"[PictureLogger] Deleted directory: {self.image_path}")
            

                
            self.timestamps.clear()
            self.frame_count = 0
            print(f"[PictureLogger] Successfully saved video to {abs_video_path}")
            
        except Exception as e:
            print(f"[PictureLogger] Error during cleanup: {e}")

    def __call__(self) -> None:
        # 确保目录在开始时就存在
        os.makedirs(self.image_path, exist_ok=True)
        video_dir = os.path.dirname(self.video_path)
        if video_dir:
            os.makedirs(video_dir, exist_ok=True)
        
        print(f"[PictureLogger] Starting to process frames...")
        
        try:
            while global_vars.pipeline_running or not self.data_queue.empty():
                try:
                    images, timestamps = self.data_queue.get(timeout=0.5)
                except:
                    continue
                try:
                    for image, timestamp in zip(images, timestamps):
                        self.save_image(self.frame_count, image, timestamp)
                        self.frame_count += 1
                except Exception as e:
                    print(f"[PictureLogger] Error processing image: {e}")
                    continue
        except Exception as e:
            print(f"[PictureLogger] Error in main loop: {e}")
        
        

        print(f"[PictureLogger] Finished processing. Saved {self.frame_count} images to {self.image_path}")
        
        # 创建视频
        if self.frame_count > 0:
            print(f"[PictureLogger] Creating video from {self.frame_count} frames...")
            try:
                self.save_video()
                print(f"[PictureLogger] Video creation completed successfully")
            except Exception as e:
                print(f"[PictureLogger] Error creating video: {e}")
        else:
            print("[PictureLogger] No frames captured, skipping video creation")
        
        print(f"[PictureLogger] Thread completed")
