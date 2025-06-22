# sender.py
import serial
import random
import time

# 初始化串口（请根据需要修改端口名和波特率）
ser = serial.Serial(
    port="/dev/ttyS1",
    baudrate=115200,
    timeout=0.5,
    bytesize = serial.EIGHTBITS,
    parity = serial.PARITY_NONE,
    stopbits = serial.STOPBITS_ONE,
)
time.sleep(2)  # 等待串口初始化

# 构造数据
middle = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=11000))
data = 'OKAY' + middle + 'OKAY'

# 发送数据
ser.write(data.encode('utf-8'))
print(f"Sent {len(data)} characters.")
ser.close()
