import cv2
import time
import os
import numpy as np
import threading
import global_vars
from queue import Queue
import subprocess
import glob

class PictureLogger():
    def __init__(self, config: dict) -> None:
        self.video_path = config["video_path"]
        self.data_queue = config["data_queue"]
        self.image_path = config["image_path"]
        self.lock = threading.Lock()

        self.timestamps = []
        self.frame_count = 0
        
        # 确保目录存在
        os.makedirs(self.image_path, exist_ok=True)
        # 确保视频文件的目录存在
        os.makedirs(os.path.dirname(self.video_path), exist_ok=True)

    def save_image(self, index: int, image: np.ndarray, timestamp: float) -> None:
        if image.max() <= 1.0:
            image = (image * 255).astype(np.uint8)
        if image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        filename = f"{self.image_path}/frame_{index:06d}.png"
        cv2.imwrite(filename, image)
        self.timestamps.append(timestamp)

    def save_video(self) -> None:
        # 检查是否有帧需要保存
        if self.frame_count == 0:
            print("No frames to save, skipping video creation")
            return
            
        txt_path = os.path.join(self.image_path, "timestamps.txt")
        
        # 确保视频输出目录存在
        video_dir = os.path.dirname(self.video_path)
        if video_dir and not os.path.exists(video_dir):
            os.makedirs(video_dir, exist_ok=True)
            print(f"Created video directory: {video_dir}")
        
        with open(txt_path, "w") as f:
            for i in range(self.frame_count - 1):
                dt = self.timestamps[i + 1] - self.timestamps[i]
                f.write(f"file 'frame_{i:06d}.png'\n")
                f.write(f"duration {dt:.6f}\n")
            f.write(f"file 'frame_{self.frame_count - 1:06d}.png'\n")

        # 使用绝对路径
        abs_video_path = os.path.abspath(self.video_path)
        
        cmd = [
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

        print(f"Attempting to create video at: {abs_video_path}")
        print(f"Working directory: {self.image_path}")
        print(f"Frame count: {self.frame_count}")

        try:
            # 检查 timestamps.txt 文件是否存在
            if not os.path.exists(txt_path):
                print(f"Error: timestamps.txt not found at {txt_path}")
                return
                
            result = subprocess.run(cmd, cwd=self.image_path, check=True, capture_output=True, text=True)
            print("FFmpeg stdout:", result.stdout)
            if result.stderr:
                print("FFmpeg stderr:", result.stderr)
                
        except subprocess.CalledProcessError as e:
            print(f"Error during ffmpeg execution: {e}")
            print(f"Return code: {e.returncode}")
            if e.stdout:
                print(f"Command output: {e.stdout}")
            if e.stderr:
                print(f"Command error: {e.stderr}")
            
            # 尝试备用方法
            print("Trying alternative ffmpeg command...")
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
                result = subprocess.run(backup_cmd, cwd=self.image_path, check=True, capture_output=True, text=True)
                print("Backup FFmpeg command succeeded")
            except subprocess.CalledProcessError as e2:
                print(f"Backup command also failed: {e2}")
                return

        # 清理文件
        try:
            for file_path in glob.glob(os.path.join(self.image_path, "frame_*.png")):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
            
            if os.path.exists(txt_path):
                os.remove(txt_path)
                
            self.timestamps.clear()
            self.frame_count = 0
            print(f"Successfully saved video to {abs_video_path}")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def __call__(self) -> None:
        # 确保目录在开始时就存在
        os.makedirs(self.image_path, exist_ok=True)
        video_dir = os.path.dirname(self.video_path)
        if video_dir:
            os.makedirs(video_dir, exist_ok=True)
            
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
                print(f"Error processing image: {e}")
                continue
                
        print(f"Saved {self.frame_count} images to {self.image_path}")
        if self.frame_count > 0:
            self.save_video()
        else:
            print("No frames captured, skipping video creation")
