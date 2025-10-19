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
            self.serial_port.flushInput()
            print(f"[PeripheralManager] Initialized with serial port: {serial_port}")
        except Exception as e:
            print(f"[FATAL] [PeripheralManager] Serial port initialization failed: {e}, exiting")
            os._exit(1)  # Exit if serial port initialization fails
        
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
            data_buf.append(ppg_data >> 16 & 0x3F)
            data_buf.append((ppg_data >> 8) & 0xFF)
            data_buf.append(ppg_data & 0xFF)
            self.serial_port.write(data_buf)
        except Exception as e:
            print(f"[PeripheralManager] Error sending curve data: {e}")

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
    # data format: (type("hr" or "data"), ecg, ppg)
    def __call__(self, data_queue: Queue):
        while global_vars.data_acquisition_running:
            try:
                data_type, ecg, ppg = data_queue.get(timeout=1)
                if data_type == "hr":
                    self.refresh_hr(ecg)
                elif data_type == "data":
                    self.refresh_curve(ecg, ppg)
            except queue.Empty:
                continue
            
