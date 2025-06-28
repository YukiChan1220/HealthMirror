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
        while global_vars.pipeline_running and self.cap.isOpened():
            success, frame = self.cap.read()
            timestamp = time.time()
            if not success:
                print("[Camera] Unable to read a frame", file=sys.stderr)
                continue
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_queue.put((frame, timestamp))

            success, ir_frame = self.ir_cap.read()
            timestamp = time.time()
            if not success:
                print("[Camera] Unable to read an IR frame", file=sys.stderr)
                continue
            ir_frame = cv2.cvtColor(ir_frame, cv2.COLOR_BGR2RGB) # TODO: color conversion may not be necessary for IR frames
            ir_frame_queue.put((ir_frame, timestamp))
