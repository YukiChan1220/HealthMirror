import queue
import serial
import threading
from queue import Queue
import time
from .base import PeripheralManagerBase
import os
import global_vars


class PeripheralManager(PeripheralManagerBase):
    def __init__(self, serial_port) -> None:
        try:
            self.serial_port = serial.Serial(
                port=serial_port,
                baudrate=115200,
                timeout=1
            )
            self.serial_port.reset_input_buffer()
            print(f"[PeripheralManager] Initialized with serial port: {serial_port}")
        except Exception as e:
            print(f"[FATAL] [PeripheralManager] Serial port initialization failed: {e}, exiting")
            os._exit(1)
        
        self.ecg_count = 0
        self.ppg_count = 0
        self.ecg_high = 0
        self.ecg_low = 0xFF
        self.ppg_high = 0
        self.ppg_low = 0xFF
        self.ecg_display_window_size = 8
        self.ppg_display_window_size = 3

        self.ecg_mean_alpha = 0.008
        self.ppg_mean_alpha = 0.1
        self.ecg_std_alpha = 0.008
        self.ppg_std_alpha = 0.01
        self.ecg_mean = None
        self.ppg_mean = None
        self.ecg_var = None
        self.ppg_var = None

        self.refresh_ecg = False
        self.refresh_ppg = False
        self.ecg_fs = 512
        self.ppg_fs = 100
        
    def get_battery_level(self) -> int:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytearray([0xFD, 0xFD, 0x00, 0x00, 0x00, 0x00]))
        time.sleep(0.5)  # wait for the response
        try:
            response = self.serial_port.read_all()
            print(f"[PeripheralManager] Battery level response: {response.hex()}")
            batt_level = response[0]
            return batt_level
        except Exception as e:
            print(f"[PeripheralManager] Error getting battery level: {e}")
        return -1
    
    def refresh_curve(self, ecg_data_h, ecg_data_l, ppg_data_h, ppg_data_l) -> None:
        try:
            data_buf = bytearray([0xFF, 0xFF])
            data_buf.extend([ecg_data_h, ecg_data_l, ppg_data_h, ppg_data_l])
            self.serial_port.write(data_buf)
        except Exception as e:
            print(f"[PeripheralManager] Error sending curve data: {e}, {data_buf}")

    def refresh_hr(self, hr_data) -> None:
        try:
            hr_data = int(hr_data)
            if not (0 <= hr_data <= 255):
                print(f"[PeripheralManager] Warning: HR data out of range: {hr_data}")
                return
            data_buf = bytearray([0xFE, 0xFE, hr_data, 0x00, 0x00, 0x00])
            self.serial_port.write(data_buf)
        except Exception as e:
            print(f"[PeripheralManager] Error sending HR data: {e}")

    def detrend_and_normalize(self, data, mean, var, mean_alpha, std_alpha, set_mean, set_std):
        if data is None:
            return None, mean, var
        if mean is None:
            mean = data
            var = 1e-6
        else:
            mean = mean_alpha * data + (1 - mean_alpha) * mean
            diff = data - mean
            var = std_alpha * (diff * diff) + (1 - std_alpha) * var

        std = var ** 0.5 + 1e-6
        normalized_data = int((data - mean) / std * set_std + set_mean)  # normalize to mean 128, std 128
        return normalized_data, mean, var
    

    # automatically fetch data from the queue
    def __call__(self, hr_queue: Queue, ecg_queue: Queue, ppg_queue: Queue) -> None:
        while global_vars.data_acquisition_running:
            try:
                hr = None
                while not hr_queue.empty():
                    hr = hr_queue.get_nowait()
                if hr is not None:
                    self.refresh_hr(hr)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing HR data: {e}")
                
            try:
                ecg = None
                while not ecg_queue.empty():
                    ecg = ecg_queue.get_nowait()[1]
                if ecg is not None:
                    ecg, self.ecg_mean, self.ecg_var = self.detrend_and_normalize(ecg, self.ecg_mean, self.ecg_var, self.ecg_mean_alpha, self.ecg_std_alpha, 48, 24)
                    ecg = max(0, min(255, int(ecg)))
                    if self.ecg_count < self.ecg_display_window_size:
                        if ecg > self.ecg_high:
                            self.ecg_high = ecg
                        if ecg < self.ecg_low:
                            self.ecg_low = ecg
                        self.ecg_count += 1
                    else:
                        if ecg > self.ecg_high:
                            self.ecg_high = ecg
                        if ecg < self.ecg_low:
                            self.ecg_low = ecg
                        self.refresh_ecg = True
                        self.ecg_count = 0
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing ECG data: {e}")

            try:
                ppg = None
                while not ppg_queue.empty():
                    ppg = ppg_queue.get_nowait()
                if ppg is not None:
                    ppg, self.ppg_mean, self.ppg_var = self.detrend_and_normalize(ppg, self.ppg_mean, self.ppg_var, self.ppg_mean_alpha, self.ppg_std_alpha, 156, 32)
                    ppg = max(0, min(255, int(ppg)))
                    if self.ppg_count < self.ppg_display_window_size:
                        if ppg > self.ppg_high:
                            self.ppg_high = ppg
                        if ppg < self.ppg_low:
                            self.ppg_low = ppg
                        self.ppg_count += 1
                    else:
                        if ppg > self.ppg_high:
                            self.ppg_high = ppg
                        if ppg < self.ppg_low:
                            self.ppg_low = ppg
                        self.refresh_ppg = True
                        self.ppg_count = 0
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing PPG data: {e}")

            if self.refresh_ecg and self.refresh_ppg:
                self.refresh_curve(self.ecg_high, self.ecg_low, self.ppg_high, self.ppg_low)
                if self.refresh_ecg:
                    self.ecg_high = 0
                    self.ecg_low = 0xFF
                    self.refresh_ecg = False
                if self.refresh_ppg:
                    self.ppg_high = 0
                    self.ppg_low = 0xFF
                    self.refresh_ppg = False
            
            time.sleep(0.005)
                
        self.ecg_count = 0
        self.ppg_count = 0
        self.ecg_high = 0
        self.ecg_low = 0xFF
        self.ppg_high = 0
        self.ppg_low = 0xFF
        self.ecg_display_window_size = 8
        self.ppg_display_window_size = 3

        self.ecg_mean_alpha = 0.008
        self.ppg_mean_alpha = 0.1
        self.ecg_std_alpha = 0.008
        self.ppg_std_alpha = 0.01
        self.ecg_mean = None
        self.ppg_mean = None
        self.ecg_var = None
        self.ppg_var = None

        self.refresh_ecg = False
        self.refresh_ppg = False
        self.ecg_fs = 512
        self.ppg_fs = 100
            
