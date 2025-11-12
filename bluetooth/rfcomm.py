import bluetooth
import os
import threading
from collections import deque

class RFCOMMSocket:
    def __init__(self, device_name: str):
        self.buffer_size = 1024
        self.waiting_buffer = deque(maxlen=self.buffer_size)

        self.device_name = device_name
        os.system("sdptool add SP")

        self.client_sock = None
        self.client_info = None

        self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.server_sock.bind(("", bluetooth.PORT_ANY))
        self.server_sock.listen(1)

        port = self.server_sock.getsockname()[1]

        bluetooth.advertise_service(self.server_sock, f"{device_name}Server",
            service_id="00001101-0000-1000-8000-00805F9B34FB",
            service_classes=["00001101-0000-1000-8000-00805F9B34FB", bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE])
        
        print(f"[Bluetooth] Listening on RFCOMM port {port}...")

        # listen for a connection
        self.client_sock, self.client_info = self.server_sock.accept()
        print(f"[Bluetooth] Connected to {self.client_info}")

    def write(self, data: bytes):
        if not self.client_sock:
            raise ConnectionError("[Bluetooth] No client is connected.")
        self.client_sock.send(data)
         
    def readline(self) -> bytes:
        if not self.client_sock:
            raise ConnectionError("[Bluetooth] No client is connected.")
        line = bytearray()
        while True:
            self._poll_read()
            while self.waiting_buffer:
                byte = self.waiting_buffer.popleft()
                line += byte
                if byte == b'\n':
                    return bytes(line)

    def _poll_read(self) -> bytes:
        if not self.client_sock:
            raise ConnectionError("[Bluetooth] No client is connected.")
        while True:
            try:
                data = self.client_sock.recv(1)
                if data:
                    self.waiting_buffer.append(data)
                    break
            except OSError:
                print("[Bluetooth] Connection lost, attempting to reconnect...")
                self._attempt_reconnect()

    def _attempt_reconnect(self):
        self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.server_sock.bind(("", bluetooth.PORT_ANY))
        self.server_sock.listen(1)

        port = self.server_sock.getsockname()[1]

        bluetooth.advertise_service(self.server_sock, self.device_name,
            service_id="00001101-0000-1000-8000-00805F9B34FB",
            service_classes=["00001101-0000-1000-8000-00805F9B34FB", bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE])
        
        print(f"[Bluetooth] Listening on RFCOMM port {port}...")

        # listen for a connection
        self.client_sock, self.client_info = self.server_sock.accept()
        print(f"[Bluetooth] Connected to {self.client_info}")

    def close(self):
        if self.client_sock:
            self.client_sock.close()
            self.client_sock = None
        if self.server_sock:
            self.server_sock.close()
            self.server_sock = None

    # TODO: deprecate or implement properly
    @property
    def in_waiting(self) -> int:
        return len(self.waiting_buffer)
