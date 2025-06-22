from queue import Queue
import onnxruntime as ort
import numpy as np
from .base import ModelBase
import global_vars


class PhysNet(ModelBase):
    def __init__(self, model_path: str):
        super().__init__()
        self.model = ort.InferenceSession(model_path)

    def __call__(self, preprocess_queue: Queue, result_queue: Queue):
        while global_vars.pipeline_running:
            frame, timestamp = preprocess_queue.get()
            batch = np.array([frame]).astype("float64") / 255.0
            input_dict = {"x.1": batch}
            result = self.model.run(None, input_dict)
            result_queue.put((result[0][0], timestamp))
