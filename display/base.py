from queue import Queue
from abc import abstractmethod


class DisplayBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self, display_queue: Queue, refresh_interval: int) -> None:
        pass
