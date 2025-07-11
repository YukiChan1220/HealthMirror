import threading
import serial
import time


class BMD101:
    def __init__(self, serial_port):
        # self.lock = threading.RLock()
        try:
            self.serial_port = serial.Serial(
                port=serial_port,
                baudrate=57600,
                timeout=0.1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self.flush_buffer()
            
            
        except Exception as e:
            print("Serial unavailable {}: {}".format(serial_port, e))
            return
        
    def flush_buffer(self):
        self.serial_port.reset_input_buffer()

    def read_data(self):
        """
        read bmd101 data from serial
        return value：
          - ret：0 success, -1 fail
          - heart_rate
          - raw_data
          - timestamp: 数据实际读取完成的时间戳
        """
        # with self.lock:
        self.serial_port.reset_input_buffer()
        start_time = time.time()
        payload_data = []

        # wait for sync bytes 0xAA, 0xAA
        byte1 = self.serial_port.read(1)[0]
        if byte1 is None or byte1 != 0xAA:
            return -1, None, None, None
            
        byte2 = self.serial_port.read(1)[0]
        if byte2 is None or byte2 != 0xAA:
            return -1, None, None, None
            
        # read payloadLength, continue if 0xAA
        payload_length = self.serial_port.read(1)[0]
        while payload_length == 0xAA:
            payload_length = self.serial_port.read(1)[0]

        if payload_length > 169:
            # illegal
            return -1, None, None, None

        generated_checksum = 0
        # read payload data
        payload_data = self.serial_port.read(payload_length)
        if len(payload_data) != payload_length:
            # not enough data
            print(f"[BMD101] Expected {payload_length} bytes, received {len(payload_data)} bytes")
            return -1, None, None, None
        for b in payload_data:
            generated_checksum += b

        checksum = self.serial_port.read(1)[0]
        generated_checksum = (255 - (generated_checksum & 0xFF)) & 0xFF

        if checksum != generated_checksum:
            # check
            return -1, None, None, None

        # unpack payload
        i = 0
        big_packet = False
        new_raw_data = False
        error_rate = 0
        heart_rate = 0
        raw_data = 0

        while i < len(payload_data):
            byte_val = payload_data[i]
            if byte_val == 0x02:
                big_packet = True
                i += 1
                if i < len(payload_data):
                    error_rate = payload_data[i]
            elif byte_val == 0x03:
                i += 1
                if i < len(payload_data):
                    heart_rate = payload_data[i]
                i += 14
            elif byte_val == 0x80:
                new_raw_data = True
                i += 1
                if i < len(payload_data):
                    v_length = payload_data[i]
                    i += 1
                    raw_data = 0
                    # Use little-endian parsing
                    for j in range(v_length):
                        if i + v_length - j - 1 < len(payload_data):
                            raw_data = raw_data | (payload_data[i + v_length - j - 1] << (8 * j))

                    if raw_data >= 32768:  # 0x8000
                        raw_data = raw_data - 65536  # Convert to negative
                        
                    i += v_length - 1  # Adjust index
                    continue
            i += 1

        # 在数据读取完成后生成时间戳
        end_time = time.time()
        
        if new_raw_data == False:
            return -1, heart_rate, raw_data, None
        else:
            return 0, heart_rate, raw_data, end_time