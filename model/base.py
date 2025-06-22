from abc import abstractmethod
from queue import Queue


class ModelBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self, preprocess_queue: Queue, result_queue: Queue):
        pass
