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
        self.should_stop = False  # 添加停止标志

    def stop_capture(self):
        """停止数据采集"""
        self.should_stop = True
        print("[Camera] Stop capture requested")

    def __call__(self, frame_queue: Queue, ir_frame_queue: Queue) -> None:
        print("[Camera] Starting camera capture thread")
        
        # 在每次采集开始时检查并重新初始化摄像头
        if not self.cap or not self.cap.isOpened() or not self.ir_cap or not self.ir_cap.isOpened():
            print("[Camera] Cameras not available, attempting to reinitialize...")
            if not self.reinitialize_cameras():
                print("[Camera] Failed to reinitialize cameras, aborting capture")
                return
        
        # 再次检查摄像头状态
        if not self.cap or not self.cap.isOpened():
            print("[Camera] RGB camera is not available or not opened")
            return
            
        if not self.ir_cap or not self.ir_cap.isOpened():
            print("[Camera] IR camera is not available or not opened")
            return
        
        print("[Camera] Cameras initialized successfully, starting capture loop")
        
        try:
            while global_vars.pipeline_running and not self.should_stop and self.cap.isOpened() and self.ir_cap.isOpened():
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
        # 重置停止标志
        self.should_stop = False
        
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
    
    def reinitialize_cameras(self):
        """重新初始化摄像头"""
        print("[Camera] Reinitializing cameras...")
        
        # 释放旧的摄像头资源
        self.cleanup()
        
        # 重新创建摄像头对象
        # 需要从外部传入摄像头路径
        if hasattr(self, 'rgb_cam_path') and hasattr(self, 'ir_cam_path'):
            try:
                self.cap = cv2.VideoCapture(self.rgb_cam_path)
                self.ir_cap = cv2.VideoCapture(self.ir_cam_path)
                
                # 检查摄像头是否成功打开
                if self.cap.isOpened() and self.ir_cap.isOpened():
                    print("[Camera] Cameras reinitialized successfully")
                    return True
                else:
                    print("[Camera] Failed to reinitialize cameras")
                    return False
            except Exception as e:
                print(f"[Camera] Error reinitializing cameras: {e}")
                return False
        else:
            print("[Camera] Camera paths not available for reinitialization")
            return False
    
    def set_camera_paths(self, rgb_cam_path, ir_cam_path):
        """设置摄像头路径，用于重新初始化"""
        self.rgb_cam_path = rgb_cam_path
        self.ir_cam_path = ir_cam_path
