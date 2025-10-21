from .bmd101 import BMD101
import time
from queue import Queue
from .base import ECGBase
import global_vars

class ECG(ECGBase):
    def __init__(self, config: dict) -> None:
        self.bmd101 = BMD101(config["bmd101"]["serial_port"])

    def stop_capture(self):
        print("[ECG] Stop capture requested")
    
    def cleanup(self):
        print("[ECG] ECG resources cleaned up")

    def read_bmd101(self) -> None:
        ret, heart_rate, raw_data, timestamp = self.bmd101.read_data()
        if ret != -1 and timestamp is not None:
            return [timestamp, raw_data]
        return None

    def filter_data(self, raw_ecg_queue: Queue, filtered_ecg_queue) -> None:
        # TODO: Implement filtering logic
        pass

    def __call__(self, raw_ecg_queue: Queue, monitor_ecg_queue: Queue) -> None:
        self.bmd101.flush_buffer()
        while global_vars.pipeline_running and global_vars.data_acquisition_running:
            ecg_data = self.read_bmd101()
            if ecg_data is not None:
                raw_ecg_queue.put(ecg_data)
                monitor_ecg_queue.put(ecg_data)
            else:
                time.sleep(0.001)
        
        print("[ECG] ECG thread stopped - data acquisition finished")