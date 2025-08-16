from queue import Queue, Full, Empty
import mediapipe as mp
import numpy as np
import cv2
import time
from typing import Any
import global_vars
from .base import PreprocessBase

# 从第二个脚本中提取卡尔曼滤波类
class KalmanFilter1D:
    def __init__(self, process_noise, measurement_noise, initial_state, initial_estimate_error, reference_interval=1/30):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.estimate = initial_state
        self.estimate_error = initial_estimate_error
        self.reference_interval = reference_interval
    
    def update(self, measurement, dt=None):
        if dt is None:
            dt = self.reference_interval
        time_scale = dt / self.reference_interval
        adjusted_process_noise = self.process_noise * (time_scale ** 2)
        prediction = self.estimate
        prediction_error = self.estimate_error + adjusted_process_noise
        kalman_gain = prediction_error / (prediction_error + self.measurement_noise)
        self.estimate = prediction + kalman_gain * (measurement - prediction)
        self.estimate_error = (1 - kalman_gain) * prediction_error
        return self.estimate

# 初始化MediaPipe FaceDetection
BaseOptions = mp.tasks.BaseOptions
FaceDetector = mp.tasks.vision.FaceDetector
FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
VisionRunningMode = mp.tasks.vision.RunningMode

class MediaPipePreprocess(PreprocessBase):
    def __init__(self, params):
        super().__init__()
        self.target_size = params["target_size"]
        self.mesh_display = params["mesh_display"]
        
        # 初始化人脸检测器（使用静态图像模式）
        model_asset_path = 'weights/blaze_face_short_range.tflite'  # 确保路径正确
        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_asset_path),
            running_mode=VisionRunningMode.IMAGE
        )
        self.face_detector = FaceDetector.create_from_options(options)
        
        # 卡尔曼滤波器初始化
        self.kalman_filters = None  # 将在首次检测时初始化
        self.last_detection_time = time.time()

    def detect_face(self, image: np.ndarray):
        """使用MediaPipe FaceDetection检测人脸并返回归一化边界框"""
        # 转换为MediaPipe图像格式
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        detection_result = self.face_detector.detect(mp_image)
        if detection_result.detections:
            # 获取第一个检测到的人脸
            face = detection_result.detections[0]
            bbox = face.bounding_box
            height, width, _ = image.shape
            
            # 转换为归一化坐标 [x_min, y_min, x_max, y_max]
            x_min = bbox.origin_x / width
            y_min = bbox.origin_y / height
            x_max = (bbox.origin_x + bbox.width) / width
            y_max = (bbox.origin_y + bbox.height) / height
            box_height = y_max - y_min
            y_min -= 0.2 * box_height
            #y_max -= 0.1 * box_height
            
            return np.array([x_min, y_min, x_max, y_max])
        return None

    def update_kalman(self, box):
        """使用卡尔曼滤波器更新边界框"""
        current_time = time.time()
        dt = current_time - self.last_detection_time
        self.last_detection_time = current_time
        
        if self.kalman_filters is None:
            # 首次检测，初始化卡尔曼滤波器
            self.kalman_filters = [
                KalmanFilter1D(0.01, 0.5, box[0], 1),  # x_min
                KalmanFilter1D(0.01, 0.5, box[1], 1),  # y_min
                KalmanFilter1D(0.01, 0.5, box[2], 1),  # x_max
                KalmanFilter1D(0.01, 0.5, box[3], 1)   # y_max
            ]
        else:
            # 更新卡尔曼滤波器
            box[0] = self.kalman_filters[0].update(box[0], dt)
            box[1] = self.kalman_filters[1].update(box[1], dt)
            box[2] = self.kalman_filters[2].update(box[2], dt)
            box[3] = self.kalman_filters[3].update(box[3], dt)
        
        return np.clip(box, 0, 1.0)

    def crop_resize(self, image: np.ndarray, size: tuple[int, int]) -> Any:
        """使用FaceDetection+卡尔曼滤波裁剪并调整人脸大小"""
        height, width, _ = image.shape
        raw_image = np.copy(image)
        
        # 检测人脸
        box = self.detect_face(image)
        
        if box is not None:
            # 应用卡尔曼滤波
            box = self.update_kalman(box)
            
            # 裁剪并调整大小
            x_min, y_min, x_max, y_max = box
            cropped = image[
                int(y_min * height):int(y_max * height),
                int(x_min * width):int(x_max * width)
            ]
            
            if cropped.size == 0:
                return None, raw_image
                
            cropped_resized = cv2.resize(
                cropped.astype("float32"),
                size,
                interpolation=cv2.INTER_AREA
            )
            return cropped_resized, raw_image
        else:
            # 未检测到人脸时重置卡尔曼滤波器
            self.kalman_filters = None
            return None, raw_image

    def __call__(self, frame_queue: Queue, preprocess_queue: Queue, log_queue: Queue, log_queue1: Queue, batch_size: int):
        cropped_frames = []
        timestamps = []
        size = 0
        n = 0
        while global_vars.pipeline_running:
            try:
                # 使用超时避免无限阻塞
                frame, timestamp = frame_queue.get(timeout=0.1)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                #cv2.imwrite(f'cache/test{x} {n:06d}.jpg', frame)
                n += 1
                preprocessed, raw = self.crop_resize(frame, self.target_size)
                if preprocessed is not None:
                    cropped_frames.append((preprocessed, raw))
                    timestamps.append(timestamp)
                    size += 1
                if size >= batch_size:
                    if preprocess_queue is not None:
                        try:
                            preprocess_queue.put((cropped_frames, timestamps), timeout=0.1)
                        except Full:
                            print("[Preprocess] Warning: preprocess_queue is full, dropping batch")
                    try:
                        log_queue.put((cropped_frames, timestamps), timeout=0.1)
                        log_queue1.put((cropped_frames, timestamps), timeout=0.1)
                    except Full:
                        print("[Preprocess] Warning: log_queue is full, dropping batch")
                    cropped_frames = []
                    timestamps = []
                    size = 0
            except Empty:
                # 队列为空时，短暂休眠后继续检查退出条件
                time.sleep(0.01)
                continue
            except Exception as e:
                # 其他异常时记录错误并继续
                print(f"[Preprocess] Error in preprocessing: {e}")
                time.sleep(0.01)
                continue
        
        # 处理剩余的数据
        if size > 0:
            print(f"[Preprocess] Processing remaining {size} frames")
            if preprocess_queue is not None:
                try:
                    preprocess_queue.put((cropped_frames, timestamps), timeout=0.1)
                except Full:
                    print("[Preprocess] Warning: preprocess_queue is full, dropping final batch")
            try:
                log_queue.put((cropped_frames, timestamps), timeout=0.1)
            except Full:
                print("[Preprocess] Warning: log_queue is full, dropping final batch")

        print("[Preprocess] Preprocessing thread stopped")
