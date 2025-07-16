from queue import Queue
import cv2
import sys
import time
from .base import CaptureBase
import global_vars


class CameraCapture(CaptureBase):
    def __init__(self, cap: cv2.VideoCapture, ir_cap: cv2.VideoCapture) -> None:
        super().__init__()
        self.cap = cap
        self.ir_cap = ir_cap

    def __call__(self, frame_queue: Queue, ir_frame_queue: Queue) -> None:
        print("[Camera] Starting camera capture thread")
        
        # Check if cameras are available
        if not self.cap or not self.cap.isOpened():
            print("[Camera] RGB camera is not available or not opened")
            return
            
        if not self.ir_cap or not self.ir_cap.isOpened():
            print("[Camera] IR camera is not available or not opened")
            return
        
        try:
            while global_vars.pipeline_running and self.cap.isOpened() and self.ir_cap.isOpened():
                # 检查队列是否已满，避免阻塞
                if frame_queue.full():
                    print("[Camera] Frame queue is full, skipping frame")
                    time.sleep(0.001)  # 短暂休眠避免忙等
                    continue
                
                if ir_frame_queue.full():
                    print("[Camera] IR frame queue is full, skipping frame")
                    time.sleep(0.001)  # 短暂休眠避免忙等
                    continue
                
                # 读取RGB帧
                try:
                    success, frame = self.cap.read()
                    timestamp = time.time()
                    if not success:
                        print("[Camera] Unable to read a frame", file=sys.stderr)
                        time.sleep(0.001)  # 短暂休眠避免忙等
                        continue
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 非阻塞put，使用timeout
                    try:
                        frame_queue.put((frame, timestamp), timeout=0.1)
                    except:
                        print("[Camera] Frame queue put timeout, skipping frame")
                        continue
                        
                except Exception as e:
                    print(f"[Camera] Error reading RGB frame: {e}")
                    time.sleep(0.001)
                    continue

                # 读取IR帧
                try:
                    success, ir_frame = self.ir_cap.read()
                    timestamp = time.time()
                    if not success:
                        print("[Camera] Unable to read an IR frame", file=sys.stderr)
                        time.sleep(0.001)  # 短暂休眠避免忙等
                        continue
                    ir_frame = cv2.cvtColor(ir_frame, cv2.COLOR_BGR2RGB) # TODO: color conversion may not be necessary for IR frames
                    
                    # 非阻塞put，使用timeout
                    try:
                        ir_frame_queue.put((ir_frame, timestamp), timeout=0.1)
                    except:
                        print("[Camera] IR frame queue put timeout, skipping frame")
                        continue
                        
                except Exception as e:
                    print(f"[Camera] Error reading IR frame: {e}")
                    time.sleep(0.001)
                    continue
                
                # 防止CPU过载
                time.sleep(0.001)
                
        except Exception as e:
            print(f"[Camera] Critical error in camera capture: {e}")
        finally:
            print("[Camera] Camera capture thread finished")
    
    def cleanup(self):
        """Clean up camera resources"""
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
                print("[Camera] RGB camera released")
        except Exception as e:
            print(f"[Camera] Error releasing RGB camera: {e}")
        
        try:
            if self.ir_cap and self.ir_cap.isOpened():
                self.ir_cap.release()
                print("[Camera] IR camera released")
        except Exception as e:
            print(f"[Camera] Error releasing IR camera: {e}")
    
    def is_opened(self):
        """Check if cameras are opened"""
        return (self.cap and self.cap.isOpened()) or (self.ir_cap and self.ir_cap.isOpened())
