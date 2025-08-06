import global_vars
from .base import BluetoothBase
from .spp import SerialSPP
from queue import Queue
import json
import time
import threading
import os

class Bluetooth(BluetoothBase):
    def __init__(self):
        # TODO: ? super().__init__()
        try:
            self.serialSPP = SerialSPP("HealthMirror02", "/dev/ttyS4", 115200, 115200)
        except Exception as e:
            print(f"[FATAL] [Bluetooth] Failed to initialize SerialSPP: {e}, exiting")
            os._exit(1)  # Exit if SerialSPP initialization fails
            self.serialSPP = None
        cmd_failed = self.serialSPP()
        if cmd_failed == 0:
            print("[Bluetooth] SPP module initialized successfully.")
        else:
            print(f"[Bluetooth] SPP module initialization failed with {cmd_failed} command(s) failed.")
        self.serial = self.serialSPP.serial
        self.transmit_interval = 0.2
    
    def listen(self, rx_data: Queue):
        # create a serial listener with json decoding
        while True:
            try:
                if self.serial.in_waiting > 0:
                    time.sleep(self.transmit_interval)
                    data = self.serial.read(self.serial.in_waiting).decode('utf-8')
                    if data:
                        try:
                            json_data = json.loads(data)
                            rx_data.put(json_data)
                            global_vars.bluetooth_interrupt = True
                            print(f"[Bluetooth] Received data: {json_data}")
                        except json.JSONDecodeError:
                            print("[Bluetooth] Failed to decode JSON data")
                else:
                    # 没有数据时休眠，减少CPU占用
                    time.sleep(0.02)  # 20ms休眠
            except Exception as e:
                print(f"[Bluetooth] Error in listen loop: {e}")
                time.sleep(0.1)  # 出错时休眠更长时间

    def send(self, tx_data: Queue):
        # create a serial sender with json encoding
        while True:
            try:
                if not tx_data.empty():
                    data = tx_data.get()
                    json_data = self.encode_json(data)
                    if json_data:
                        try:
                            self.serial.write(json_data.encode('utf-8'))
                            print(f"[Bluetooth] Sent data: {json_data}")
                        except Exception as e:
                            print(f"[Bluetooth] Failed to send data: {e}")
                    time.sleep(self.transmit_interval)
                else:
                    # 队列为空时休眠，减少CPU占用
                    time.sleep(0.02)  # 10ms休眠
            except Exception as e:
                print(f"[Bluetooth] Error in send loop: {e}")
                time.sleep(0.1)  # 出错时休眠更长时间

    def encode_json(self, data: dict) -> str:
        """Encode a dictionary to a JSON string."""
        try:
            json_data = json.dumps(data)
            return json_data + '\r\n'  # Add newline for SPP protocol
        except (TypeError, ValueError) as e:
            print(f"[Bluetooth] Failed to encode data to JSON: {e}")
            return None

    def __call__(self, tx_data: Queue, rx_data: Queue):
        threads = []
        # create a thread for listening
        listen_thread = threading.Thread(target=self.listen, args=(rx_data,), daemon=True, name="BluetoothListenThread")
        threads.append(listen_thread)
        # create a thread for sending
        send_thread = threading.Thread(target=self.send, args=(tx_data,), daemon=True, name="BluetoothSendThread")
        threads.append(send_thread)
        # start the threads
        for thread in threads:
            thread.daemon = True
            thread.start()
        
        print("[Bluetooth] Bluetooth listen/send threads started")
        
        # Store threads for potential cleanup
        self.threads = threads




