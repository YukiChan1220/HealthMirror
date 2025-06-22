from queue import Queue
from bluetooth.listen import Bluetooth  # 假设 Bluetooth 类在 bluetooth/listen.py 中定义

tx_queue = Queue()
rx_queue = Queue()

bluetooth = Bluetooth()
bluetooth(tx_queue, rx_queue)  # 启动监听和发送线程

# 向 tx_queue 放入要发送的字典
tx_queue.put({"command": "start", "value": 1})

# 在主线程中轮询 rx_queue 读取接收结果
while True:
    if not rx_queue.empty():
        data = rx_queue.get()
        print(f"Main received: {data}")
