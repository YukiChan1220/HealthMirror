from queue import Queue
import pickle
import onnxruntime as ort
import numpy as np
from .base import ModelBase
import global_vars


class Step(ModelBase):
    def __init__(self, model_path, state_path, dt: float):
        super().__init__()
        self.model_path = model_path
        self.state_path = state_path
        self.model = ort.InferenceSession(model_path)
        with open(state_path, "rb") as f:
            self.state = pickle.load(f)
        self.dt = np.array(dt).astype("float16")

    def __call__(self, preprocess_queue: Queue, result_queue: Queue):
        while global_vars.pipeline_running:
            # TODO: Calculate `dt` dynamically
            try:
                frame, timestamp = preprocess_queue.get(timeout=0.5)
            except:
                continue
            image = np.array([frame]).astype("float16") / 255.0
            input_dict = {"arg_0.1": image, "onnx::Mul_37": self.dt, **self.state}
            result = self.model.run(None, input_dict)
            self.state = dict(zip(list(input_dict)[2:], result[1:]))
            result_queue.put([[result[0][0, 0]], timestamp])
        with open(self.state_path, "wb") as f:
            pickle.dump(self.state, f)
