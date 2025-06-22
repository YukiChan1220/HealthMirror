from abc import abstractmethod
from queue import Queue


class ECGBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self, raw_ecg_queue: Queue, filtered_ecg_queue: Queue):
        pass