import serial
import threading
import queue
import time
from .base import PeripheralManagerBase
import os


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
        self.serial_port.write(b'get_batt\n')
        response = self.serial_port.readline().strip()
        if response.isdigit():
            batt_level = int((int(response) - 68) / 18 * 100)
            return batt_level if 0 <= batt_level <= 100 else 0
        return -1
    
    def refresh_display(self, number: int) -> None:
        self.serial_port.write(f'{number}\n'.encode())
        
