# receiver.py
import serial
import time

# 初始化串口
ser = serial.Serial(
    port="COM29",
    baudrate=115200,
    timeout=0.5,
    bytesize = serial.EIGHTBITS,
    parity = serial.PARITY_NONE,
    stopbits = serial.STOPBITS_ONE,
)

buffer = ''
recording = False
start_time = None
end_time = None
received_data = ''

while True:
    if ser.in_waiting > 0:
        char = ser.read().decode('utf-8', errors='ignore')
        buffer += char

        # 保持缓冲区最多只保留最近4个字符
        if len(buffer) > 4:
            buffer = buffer[-4:]

        if buffer == 'OKAY':
            if not recording:
                print("Start received")
                recording = True
                received_data = ''
                start_time = time.time()
            else:
                end_time = time.time()
                duration = end_time - start_time
                char_count = len(received_data)
                rate = char_count / duration if duration > 0 else 0
                print(f"End received")
                print(f"Received {char_count} characters in {duration:.3f} seconds")
                print(f"Rate: {rate:.2f} chars/second")
                break
        elif recording:
            received_data += char

ser.close()
