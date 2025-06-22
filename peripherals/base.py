from abc import abstractmethod


class PeripheralsBase:
    def __init__(self):
        pass

    @abstractmethod
    def __call__(self):
        pass