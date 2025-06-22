import serial
import time

class SerialSPP:
    baudrate = {
        9600: "4",
        19200: "5",
        38400: "6",
        57600: "7",
        115200: "8",
        128000: "9",
    }

    def __init__(self, device_name, serial_port, init_baudrate, set_baudrate):
        self.device_name = device_name
        self.serial = serial.Serial(
            port=serial_port,
            baudrate=init_baudrate,
            timeout=1,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            
        )
        self.init_baudrate = init_baudrate
        self.set_baudrate = set_baudrate

    def send_command(self, command: str) -> str:
        """Send a command to the SPP module and return the response."""
        self.serial.write(f'{command}\r\n'.encode())
        time.sleep(0.1)
        response = self.serial.read(self.serial.in_waiting).decode('utf-8').strip()
        time.sleep(0.2)  # 等待一段时间以确保数据被接收
        if response.endswith('OK'):
            print(f"Command successful: {command}, Response: {response}")
            return 0
        else:
            print(f"Command failed: {command}, Response: {response}")
            return -1
        

    def init_spp(self) -> int:
        status = self.send_command('AT+RESET')
        status += self.send_command(f'AT+BAUD{self.baudrate[self.init_baudrate]}')
        status += self.send_command(f'AT+NAME{self.device_name}')
        return status
    
    def __call__(self):
        return self.init_spp()