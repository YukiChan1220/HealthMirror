import serial
import threading
import queue
import time
from .base import PeripheralManagerBase


class PeripheralManager(PeripheralManagerBase):
    def __init__(self, serial_port) -> None:
        self.serial_port = serial.Serial(
            port=serial_port,
            baudrate=115200,
            timeout=1
        )
        
    def get_battery_level(self) -> int:
        self.serial_port.write(b'batt\n')
        response = self.serial_port.readline().strip()
        if response.isdigit():
            return int(response)
        return -1
    
    def refresh_display(self, number: int) -> None:
        self.serial_port.write(f'{number}\n'.encode())
        
