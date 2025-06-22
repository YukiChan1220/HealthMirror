from .tm1637 import TM1637
from .base import DisplayBase
import global_vars
import time
from queue import Queue

class Display(DisplayBase):
    def __init__(self, config: dict) -> None:
        self.tm1637 = TM1637(config["tm1637"]["data_pin"], config["tm1637"]["clk_pin"])
        self.threads = []

    def refresh_display(self, data) -> None:
        a = data // 1000
        b = data // 100 % 10
        c = data // 10 % 10
        d = data % 10
        if a == 0 & b != 0:
            self.tm1637.display([-1, b, c, d])
        elif a == 0 & b == 0:
            self.tm1637.display([-1, -1, c, d])
        else:
            self.tm1637.display([a, b, c, d])

    def clear_display(self) -> None:
        self.tm1637.display([-1, -1, -1, -1])

    def __call__(self, display_queue: Queue, refresh_interval: int) -> None:
        while global_vars.pipeline_running:
            while not display_queue.empty():
                data = display_queue.get()
                self.refresh_display(data)
            else:
                self.clear_display()
            time.sleep(refresh_interval)
