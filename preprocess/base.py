from abc import abstractmethod
from queue import Queue


class PreprocessBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self, frame_queue: Queue, preprocess_queue: Queue, side_queue: Queue, log_queue:Queue, batch_size: int):
        pass
