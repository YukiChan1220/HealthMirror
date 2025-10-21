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
        
        self.ecg_buffer = []
        self.ppg_buffer = []
        self.avg_ecg = 0
        self.avg_ppg = 0
        self.ecg_avg_count = 17
        self.ppg_avg_count = 3
        self.refresh_ecg = False
        self.refresh_ppg = False
        self.ecg_fs = 512
        self.ppg_fs = 100
        
    def get_battery_level(self) -> int:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(b'\xFD\xFD\xFD\x00\x00\x00\x00\x00')
        time.sleep(0.1)  # wait for the response
        response = self.serial_port.read(self.serial_port.in_waiting)
        print(f"[PeripheralManager] Battery level response: {response}")
        if response.isdigit():
            batt_level = int(response)
            return batt_level if 0 <= batt_level <= 100 else 0
        return -1
    
    def refresh_curve(self, ecg_data, ppg_data) -> None:
        try:
            ppg_data = int(ppg_data)
            ecg_data = int(ecg_data)
            data_buf = bytearray([0xFF, 0xFF, 0xFF])
            data_buf.append(ecg_data >> 8)
            data_buf.append(ecg_data & 0xFF)
            data_buf.append((ppg_data >> 16) & 0x3F)
            data_buf.append((ppg_data >> 8) & 0xFF)
            data_buf.append(ppg_data & 0xFF)
            self.serial_port.write(data_buf)
        except Exception as e:
            print(f"[PeripheralManager] Error sending curve data: {e}, {ecg_data}, {ppg_data}")

    def refresh_hr(self, hr_data) -> None:
        try:
            hr_data = int(hr_data)
            if not (0 <= hr_data <= 255):
                print(f"[PeripheralManager] Warning: HR data out of range: {hr_data}")
                return
            data_buf = bytearray([0xFE, 0xFE, 0xFE, hr_data, 0x00, 0x00, 0x00, 0x00])
            self.serial_port.write(data_buf)
        except Exception as e:
            print(f"[PeripheralManager] Error sending HR data: {e}")

    # automatically fetch data from the queue
    def __call__(self, hr_queue: Queue, ecg_queue: Queue, ppg_queue: Queue) -> None:
        while global_vars.data_acquisition_running:
            try:
                hr = hr_queue.get_nowait()
                if hr is not None:
                    self.refresh_hr(hr)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing HR data: {e}")
                
            try:
                ecg = ecg_queue.get_nowait()
                if ecg is not None and len(self.ecg_buffer) < 17:
                    self.ecg_buffer.append(ecg[1])
                else:
                    self.avg_ecg = (sum(self.ecg_buffer) + ecg[1]) / 17
                    self.ecg_buffer.clear()
                    self.refresh_ecg = True
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing ECG data: {e}")

            try:
                ppg = ppg_queue.get_nowait()
                if ppg is not None and len(self.ppg_buffer) < 3:
                    self.ppg_buffer.append(ppg)
                else:
                    self.avg_ppg = (sum(self.ppg_buffer) + ppg) / 3
                    self.ppg_buffer.clear()
                    self.refresh_ppg = True
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PeripheralManager] Error processing PPG data: {e}")

            if self.refresh_ecg and self.refresh_ppg:
                self.refresh_curve(self.avg_ecg + 32768, self.avg_ppg)
                self.refresh_ecg = False
                self.refresh_ppg = False
            
            time.sleep(0.005)

        self.ecg_buffer.clear()
        self.ppg_buffer.clear()
                
            
