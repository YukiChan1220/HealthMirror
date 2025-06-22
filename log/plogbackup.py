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
        txt_path = os.path.join(self.image_path, "timestamps.txt")
        with open(txt_path, "w") as f:
            for i in range(self.frame_count - 1):
                dt = self.timestamps[i + 1] - self.timestamps[i]
                f.write(f"file 'frame_{i:06d}.png'\n")
                f.write(f"duration {dt:.6f}\n")
            f.write(f"file 'frame_{self.frame_count - 1:06d}.png'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "timestamps.txt",
            "-vsync", "vfr",
            "-c:v", "mpeg4",
            "-pix_fmt", "yuv420p",
            self.video_path
        ]

        debug_cmd = [
            "ffmpeg",
            "-framerate", "30",
            "-i", "frame_%06d.png",
            "-c:v", "mpeg4",
            "-pix_fmt", "yuv420p",
            "test.mp4"
        ]

        try:
            result = subprocess.run(cmd, cwd=self.image_path, check=True, capture_output=True, text=True)
            print(result.stdout)
            print(result.stderr)
        except subprocess.CalledProcessError as e:
            print(f"Error during ffmpeg execution: {e}")
            print(f"Command output: {e.output}")
            print(f"Command error: {e.stderr}")

        for file_path in glob.glob(os.path.join(self.image_path, "frame_*.png")):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
        os.remove(txt_path)
        self.timestamps.clear()
        self.frame_count = 0
        print(f"Saved video to {self.video_path}")

    def __call__(self) -> None:
        os.makedirs(self.image_path, exist_ok=True)
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
        self.save_video()
