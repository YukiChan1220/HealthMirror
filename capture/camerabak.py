from queue import Queue
import cv2
import sys
import time
from .base import CaptureBase
import global_vars
import os


class CameraCapture(CaptureBase):
    def __init__(self, cap: cv2.VideoCapture, ir_cap: cv2.VideoCapture) -> None:
        super().__init__()
        self.cap = cap
        self.ir_cap = ir_cap
        self.frame_count = 0

    def stop_capture(self):
        """停止数据采集"""
        print("[Camera] Stop capture requested")
        self.frame_count=0

    def __call__(self, frame_queue: Queue, frame_log_queue: Queue, ir_frame_queue: Queue, ir_frame_log_queue: Queue) -> None:
        print("[Camera] Starting camera capture thread")
        self.frame_count = 0
        
        # 在每次采集开始时检查并重新初始化摄像头
        if not self.cap or not self.cap.isOpened() or not self.ir_cap or not self.ir_cap.isOpened():
            print("[Camera] Cameras not available, attempting to reinitialize...")
            if not self.reinitialize_cameras():
                print("[FATAL] [Camera] Failed to reinitialize cameras, aborting capture")
                return
        
        # 再次检查摄像头状态
        if not self.cap or not self.cap.isOpened():
            print("[FATAL] [Camera] RGB camera is not available or not opened, exiting")
            os._exit(1)
            return
            
        if not self.ir_cap or not self.ir_cap.isOpened():
            print("[FATAL] [Camera] IR camera is not available or not opened, exiting")
            os._exit(1)
            return
        
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ir_cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.ir_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        print(f"[Camera] [FPS] {self.cap.get(cv2.CAP_PROP_FPS)}, {self.ir_cap.get(cv2.CAP_PROP_FPS)}")

        print("[Camera] Cameras initialized successfully, starting capture loop")
        
        try:
            while global_vars.pipeline_running and global_vars.data_acquisition_running and self.cap.isOpened() and self.ir_cap.isOpened():
                # 检查所有队列是否已满，避免阻塞
                if frame_queue.full() or frame_log_queue.full():
                    print("[Camera] Frame queue(s) are full, skipping frame")
                    time.sleep(0.5)  # 短暂休眠避免忙等
                    if frame_queue.full() or frame_log_queue.full():
                        print("[FATAL] [Camera] Frame queue(s) are still full, exiting")
                        os._exit(1)  # 如果队列仍然满，退出程序
                    continue
                
                if ir_frame_queue.full() or ir_frame_log_queue.full():
                    print("[Camera] IR frame queue(s) are full, skipping frame")
                    time.sleep(0.5)  # 短暂休眠避免忙等
                    if ir_frame_queue.full() or ir_frame_log_queue.full():
                        print("[FATAL] [Camera] IR frame queue(s) are still full, exiting")
                        os._exit(1)  # 如果队列仍然满，退出程序
                    continue
                
                # 读取RGB帧
                try:
                    success, frame = self.cap.read()
                    # print(frame.shape)
                    timestamp = time.time()
                    if not success:
                        print("[Camera] Unable to read a frame", file=sys.stderr)
                        time.sleep(0.5)  # 短暂休眠避免忙等
                        success, frame = self.cap.read()  # 再次尝试读取
                        if not success:
                            print("[FATAL] [Camera] Unable to read a frame after retry")
                            os._exit(1)  # 如果仍然失败，退出程序
                        continue
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_count += 1
                    print(f"[Camera] Frame count: {self.frame_count}")

                    # 同时放入frame_queue和frame_log_queue，使用非阻塞put
                    try:
                        frame_queue.put((frame, timestamp), timeout=0.1)
                        # frame_log_queue.put(([frame], [timestamp]), timeout=0.1)
                    except:
                        print("[Camera] Frame queue put timeout, skipping frame")
                        continue
                        
                except Exception as e:
                    print(f"[Camera] Error reading RGB frame: {e}")
                    time.sleep(0.01)
                    continue

                # 读取IR帧
                try:
                    success, ir_frame = self.ir_cap.read()
                    timestamp = time.time()
                    if not success:
                        print("[Camera] Unable to read an IR frame", file=sys.stderr)
                        time.sleep(0.5)  # 短暂休眠避免忙等
                        success, ir_frame = self.ir_cap.read()  # 再次尝试读取
                        if not success:
                            print("[FATAL] [Camera] Unable to read an IR frame after retry")
                            os._exit(1)  # 如果仍然失败，退出程序
                        continue
                    ir_frame = cv2.cvtColor(ir_frame, cv2.COLOR_BGR2RGB) # TODO: color conversion may not be necessary for IR frames
                    
                    # 同时放入ir_frame_queue和ir_frame_log_queue，使用非阻塞put
                    try:
                        ir_frame_queue.put((ir_frame, timestamp), timeout=0.1)
                        # ir_frame_log_queue.put(([ir_frame], [timestamp]), timeout=0.1)
                    except:
                        print("[Camera] IR frame queue put timeout, skipping frame")
                        continue
                        
                except Exception as e:
                    print(f"[Camera] Error reading IR frame: {e}")
                    time.sleep(0.01)
                    continue
                
                # 防止CPU过载
                # time.sleep(0.001)
                
        except Exception as e:
            print(f"[FATAL] [Camera] Error in camera capture: {e}")
            os._exit(1)  # 如果发生严重错误，退出程序
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
                    print("[FATAL] [Camera] Failed to reinitialize cameras")
                    os._exit(1)  # 如果摄像头无法重新初始化，退出程序
                    return False
            except Exception as e:
                print(f"[FATAL] [Camera] Error reinitializing cameras: {e}")
                os._exit(1)
                return False
        else:
            print("[FATAL] [Camera] Camera paths not available for reinitialization")
            os._exit(1)
            return False
    
    def set_camera_paths(self, rgb_cam_path, ir_cam_path):
        """设置摄像头路径，用于重新初始化"""
        self.rgb_cam_path = rgb_cam_path
        self.ir_cam_path = ir_cam_path
