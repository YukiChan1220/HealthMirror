from queue import Queue, Full, Empty
import mediapipe as mp
import numpy as np
import cv2
import time
from typing import Any
import global_vars
from .base import PreprocessBase

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


class MediaPipePreprocess(PreprocessBase):
    def __init__(self, params):
        super().__init__()
        self.target_size = params["target_size"]
        self.mesh_display = params["mesh_display"]
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1
        )

    def crop_resize(self, image: np.ndarray, size: tuple[int, int]) -> Any:
        """
        Crop with mediapipe and resize an image to a given size.
        :param image: image read by cv2 and converted to RGB (cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        :param size: target image size (width, height)
        :return: cropped and resized image
        """
        height, width, _ = image.shape
        results = self.face_mesh.process(image)
        raw_image = np.copy(image)
        if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
            if self.mesh_display:
                for face_landmarks in results.multi_face_landmarks:
                    mp_drawing.draw_landmarks(
                        image=raw_image,
                        landmark_list=face_landmarks,
                        connections=mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style(),
                    )
            multi_landmarks = results.multi_face_landmarks[0]
            landmarks = np.array(
                [(landmark.x, landmark.y) for landmark in
                 multi_landmarks.landmark])
            x_min, y_min = np.min(landmarks, axis=0)
            x_max, y_max = np.max(landmarks, axis=0)
            box = np.clip(np.array([x_min, y_min, x_max, y_max]), 0, 1.0)
            cropped_resized = cv2.resize(
                image[int(box[1] * height):int(box[3] * height), int(box[0] * width):int(box[2] * width)].astype("float32"),
                size,
                interpolation=cv2.INTER_AREA
            )
            return cropped_resized, raw_image
        else:
            return None, raw_image

    def __call__(self, frame_queue: Queue, preprocess_queue: Queue, log_queue: Queue, batch_size: int):
        cropped_frames = []
        timestamps = []
        size = 0
        while global_vars.pipeline_running:
            try:
                # 使用超时避免无限阻塞
                frame, timestamp = frame_queue.get(timeout=0.5)
                preprocessed, raw = self.crop_resize(frame, self.target_size)
                if preprocessed is not None:
                    cropped_frames.append(preprocessed)
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
