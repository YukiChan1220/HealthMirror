import serial
import threading

mySerial = serial.Serial(
    port="COM29",
    baudrate=115200,
    timeout=0.5,
    bytesize = serial.EIGHTBITS,
    parity = serial.PARITY_NONE,
    stopbits = serial.STOPBITS_ONE,
)

def receive_data():
    while True:
        if mySerial.in_waiting > 0:
            line = mySerial.readline().decode('utf-8').strip()
            print(line)
            if line == "OK":
                break

# 用于发送数据的线程
def send_data():
    while True:
        user_input = input()  # 从用户获取输入
        mySerial.write(user_input.encode())  # 发送数据到串口
        print(f"{user_input} sent.")

# 创建并启动接收线程
receive_thread = threading.Thread(target=receive_data, daemon=True)
receive_thread.start()

# 创建并启动发送线程
send_thread = threading.Thread(target=send_data, daemon=True)
send_thread.start()

# 主线程等待接收线程完成（或者在特定条件下终止）
receive_thread.join()  # 等待接收线程结束