from queue import Queue
import cv2
import sys
import time
import threading
from .base import CaptureBase
import global_vars
import os


class CameraCapture(CaptureBase):
    def __init__(self, cap: cv2.VideoCapture, ir_cap: cv2.VideoCapture) -> None:
        super().__init__()
        self.cap = cap
        self.ir_cap = ir_cap
        self.rgb_frame_count = 0
        self.ir_frame_count = 0
        self.stop_event = threading.Event()

    def stop_capture(self):
        """停止数据采集"""
        print("[Camera] Stop capture requested")
        self.stop_event.set()
        self.rgb_frame_count = 0
        self.ir_frame_count = 0

    def __call__(self, frame_queue: Queue, ir_frame_queue: Queue) -> None:
        print("[Camera] Starting camera capture threads")
        
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
            
        if not self.ir_cap or not self.ir_cap.isOpened():
            print("[FATAL] [Camera] IR camera is not available or not opened, exiting")
            os._exit(1)
        
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ir_cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.ir_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        print(f"[Camera] [FPS] RGB: {self.cap.get(cv2.CAP_PROP_FPS)}, IR: {self.ir_cap.get(cv2.CAP_PROP_FPS)}")

        print("[Camera] Cameras initialized successfully, starting capture threads")
        
        # 重置停止事件
        self.stop_event.clear()
        
        # 创建并启动线程
        rgb_thread = threading.Thread(
            target=self._capture_rgb,
            args=(frame_queue,),
            daemon=True
        )
        
        ir_thread = threading.Thread(
            target=self._capture_ir,
            args=(ir_frame_queue,),
            daemon=True
        )
        
        rgb_thread.start()
        ir_thread.start()
        
        # 等待线程结束
        try:
            while rgb_thread.is_alive() or ir_thread.is_alive():
                rgb_thread.join(timeout=0.1)
                ir_thread.join(timeout=0.1)
                
                # 检查是否需要停止
                if not global_vars.pipeline_running or not global_vars.data_acquisition_running:
                    self.stop_event.set()
        except KeyboardInterrupt:
            self.stop_event.set()
        finally:
            print("[Camera] Camera capture threads finished")

    def _capture_rgb(self, frame_queue):
        """RGB摄像头采集线程"""
        print("[Camera] Starting RGB capture thread")
        self.rgb_frame_count = 0
        last_log_count = 0
        while not self.stop_event.is_set() and global_vars.pipeline_running and global_vars.data_acquisition_running:
            # 检查摄像头状态
            if not self.cap or not self.cap.isOpened():
                print("[FATAL] [Camera] RGB camera disconnected")
                os._exit(1)
                
            # 检查队列是否已满
            if frame_queue.full():
                print("[Camera] RGB frame queue is full, skipping frame")
                time.sleep(0.5)
                if frame_queue.full():
                    print("[FATAL] [Camera] RGB frame queue is still full, exiting")
                    os._exit(1)
                continue
            
            # 读取RGB帧
            try:
                success, frame = self.cap.read()
                timestamp = time.time()
                
                if not success:
                    print("[Camera] Unable to read RGB frame")
                    time.sleep(0.5)
                    success, frame = self.cap.read()
                    if not success:
                        print("[FATAL] [Camera] Unable to read RGB frame after retry")
                        os._exit(1)
                    continue
                    
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.rgb_frame_count += 1
                if self.rgb_frame_count - last_log_count >= 30:
                    last_log_count = self.rgb_frame_count
                    print(f"[Camera] RGB frame count: {self.rgb_frame_count}")
                
                # 放入队列
                try:
                    frame_queue.put((frame, timestamp), timeout=0.1)
                except:
                    print("[Camera] RGB frame queue put timeout, skipping frame")
                    
            except Exception as e:
                print(f"[Camera] Error reading RGB frame: {e}")
                time.sleep(0.01)
                
            # 防止CPU过载
            time.sleep(0.005)

    def _capture_ir(self, ir_frame_queue):
        """IR摄像头采集线程"""
        print("[Camera] Starting IR capture thread")
        self.ir_frame_count = 0
        last_log_count = 0

        while not self.stop_event.is_set() and global_vars.pipeline_running and global_vars.data_acquisition_running:
            # 检查摄像头状态
            if not self.ir_cap or not self.ir_cap.isOpened():
                print("[FATAL] [Camera] IR camera disconnected")
                os._exit(1)
                
            # 检查队列是否已满
            if ir_frame_queue.full():
                print("[Camera] IR frame queue is full, skipping frame")
                time.sleep(0.5)
                if ir_frame_queue.full():
                    print("[FATAL] [Camera] IR frame queue is still full, exiting")
                    os._exit(1)
                continue
            
            # 读取IR帧
            try:
                success, ir_frame = self.ir_cap.read()
                timestamp = time.time()
                
                if not success:
                    print("[Camera] Unable to read IR frame")
                    time.sleep(0.5)
                    success, ir_frame = self.ir_cap.read()
                    if not success:
                        print("[FATAL] [Camera] Unable to read IR frame after retry")
                        os._exit(1)
                    continue
                    
                ir_frame = cv2.cvtColor(ir_frame, cv2.COLOR_BGR2RGB) # TODO: color conversion may not be necessary for IR frames
                self.ir_frame_count += 1
                if self.ir_frame_count - last_log_count >= 30:
                    last_log_count = self.ir_frame_count
                    print(f"[Camera] IR frame count: {self.ir_frame_count}")

                # 放入队列
                try:
                    ir_frame_queue.put((ir_frame, timestamp), timeout=0.1)
                except:
                    print("[Camera] IR frame queue put timeout, skipping frame")
                    
            except Exception as e:
                print(f"[Camera] Error reading IR frame: {e}")
                time.sleep(0.01)
                
            # 防止CPU过载
            time.sleep(0.005)

    def cleanup(self):
        """Clean up camera resources"""
        self.stop_event.set()
        
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
