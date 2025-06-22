from queue import Queue
from abc import abstractmethod


class BluetoothBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self, config: dict, tx_queue: Queue, rx_queue: Queue) -> None:
        pass
