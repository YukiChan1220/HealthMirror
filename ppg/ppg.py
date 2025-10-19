import time
from queue import Queue
from typing import Optional

import global_vars

from .base import PPGBase, PPGSample
from .max30101 import MAX30101, MAX30101Config


class PPG(PPGBase):
    def __init__(self, config: dict) -> None:
        sensor_cfg = config
        bus = sensor_cfg.get("bus", 4)
        address = sensor_cfg.get("address", MAX30101.DEFAULT_ADDRESS)
        self.monitor = sensor_cfg.get("monitor", True)
        config_obj = sensor_cfg.get("config")

        if isinstance(config_obj, dict):
            config_obj = MAX30101Config(**config_obj)
        self.sensor = MAX30101(bus=bus, address=address, config=config_obj)
        self.max_queue_size = config.get("max_queue_size", 512)
        self.poll_interval = config.get("poll_interval", 0.005)

    def enable(self) -> None:
        self.sensor.enable()

    def disable(self) -> None:
        self.sensor.disable()

    def read_sample(self) -> PPGSample:
        return self.sensor.read_sample()

    def read_ppg(self) -> Optional[list]:
        try:
            sample = self.read_sample()
        except OSError:
            time.sleep(self.poll_interval)
            return None
        return [sample.timestamp, sample.red, sample.ir, sample.green]

    def close(self) -> None:
        self.sensor.close()

    def __call__(self, raw_ppg_queue: Queue, monitor_ppg_queue: Queue) -> None:
        self.enable()
        try:
            ppg_data = [0, 0, 0, 0]
            while global_vars.pipeline_running:
                if time.time() - ppg_data[0] > self.poll_interval:
                    ppg_data = self.read_ppg()
                    if ppg_data is not None:
                        raw_ppg_queue.put(ppg_data)
                        if self.monitor:
                            if monitor_ppg_queue.full():
                                monitor_ppg_queue.get_nowait()
                            monitor_ppg_queue.put(ppg_data[2])
        finally:
            self.disable()
