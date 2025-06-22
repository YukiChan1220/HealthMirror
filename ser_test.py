import serial
import time



serial = serial.Serial(
    port="/dev/ttyS1",
    baudrate=115200,
    timeout=1,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
)

while True:
    if serial.in_waiting > 0:
        data = serial.read(serial.in_waiting).decode('utf-8')
        if data:
            print(f"Received data: {data}")
    serial.write(input("Enter data to send: ").encode('utf-8') + b'\r\n')
    serial.flush()  # 确保数据被发送
    print("Data sent successfully.")
    time.sleep(0.2)  # 等待一段时间以避免过快发送


