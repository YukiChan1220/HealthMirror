from abc import abstractmethod


class PeripheralManagerBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self):
        pass