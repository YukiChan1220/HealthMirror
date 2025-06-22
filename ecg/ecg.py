from .bmd101 import BMD101
import time
from queue import Queue
from .base import ECGBase
import global_vars

class ECG(ECGBase):
    def __init__(self, config: dict) -> None:
        self.bmd101 = BMD101(config["bmd101"]["serial_port"])
        self.max_queue_size = 512

    def read_bmd101(self, raw_ecg_queue: Queue) -> None:
        timestamp = time.time()
        ret, heart_rate, raw_data = self.bmd101.read_data()
        if ret != -1:
            raw_ecg_queue.put([timestamp, raw_data])

            

    def filter_data(self, raw_ecg_queue: Queue, filtered_ecg_queue) -> None:
        # TODO: Implement filtering logic
        pass

    def __call__(self, raw_ecg_queue: Queue, filtered_ecg_queue: Queue) -> None:
        while global_vars.pipeline_running:
            self.read_bmd101(raw_ecg_queue)
            # TODO: self.filter_data(self.side_raw_queue, filtered_ecg_queue)