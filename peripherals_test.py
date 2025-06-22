from scipy.signal import butter, iirnotch, lfilter, find_peaks
from ecg.bmd101 import BMD101
from display.tm1637 import TM1637
import numpy as np
import threading
import queue
import time
import wiringpi

BUFFER_SIZE = 2048
ECG_FS = 512
heart_rate = 0
SERIAL_PORT = '/dev/ttyS0'  # 修改为你的串口
raw_data = np.zeros(BUFFER_SIZE)
filtered_data = np.zeros(BUFFER_SIZE)
raw_queue = queue.Queue()
filtered_queue = queue.Queue()
hr_queue = queue.Queue()
lock = threading.Lock()
stop_event = threading.Event()

def bandpass_filter(data, lowcut=0.5, highcut=40, fs=ECG_FS, order=2):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return lfilter(b, a, data)

def notch_filter(data, fs=ECG_FS, freq=50, Q=30):
    nyquist = 0.5 * fs
    w0 = freq / nyquist
    b, a = iirnotch(w0, Q)
    return lfilter(b, a, data)

def calculate_heart_rate(ecg_data, fs=ECG_FS):
    # Find peaks in the ECG data
    peaks, _ = find_peaks(ecg_data, distance=fs*0.4)  # Minimum distance between peaks
    if len(peaks) < 2:
        return 0  # Not enough peaks to calculate heart rate

    # Calculate RR intervals (in seconds)
    rr_intervals = np.diff(peaks) / fs
    # Calculate heart rate (in beats per minute)
    hr = 60 / np.mean(rr_intervals)
    return int(hr)

def read_bmd101_data():
    bmd101 = BMD101(SERIAL_PORT)
    while not stop_event.is_set():
        ret, hr, raw = bmd101.read_data()
        if ret != -1:
            with lock:
                # Apply filters
                global raw_data, filtered_data, heart_rate
                # put raw into raw_data
                raw_data = np.roll(raw_data, -1)
                raw_data[-1] = raw
                # Apply notch filter
                notched = notch_filter(raw_data)
                filtered_data = bandpass_filter(notched)
                # Calculate heart rate
                heart_rate = calculate_heart_rate(filtered_data)
                # Put data into queues
                raw_queue.put(raw)
                filtered_queue.put(filtered_data[-1])
                hr_queue.put(heart_rate)

def write_to_csv():
    with open("ecg_data.csv", "w") as f:
        f.write("raw_data,filtered_data,heart_rate\n")
        while not stop_event.is_set():
            try:
                raw = raw_queue.get()
                filtered = filtered_queue.get()
                hr = hr_queue.get()
                f.write(f"{raw},{filtered},{hr}\n")
            except queue.Empty:
                continue

def display_on_tm1637():
    tm1637 = TM1637(9, 10)
    while not stop_event.is_set():
        with lock:
            if heart_rate != 0:
                a = -1
                b = heart_rate // 100
                c = heart_rate // 10 % 10
                d = heart_rate % 10
                tm1637.display([a, b, c, d])
            else:
                tm1637.display([9, 9, 9, 9])
        time.sleep(0.5)

def main():
    wiringpi.wiringPiSetup()
    # Start threads
    bmd101_thread = threading.Thread(target=read_bmd101_data)
    csv_thread = threading.Thread(target=write_to_csv)
    display_thread = threading.Thread(target=display_on_tm1637)

    bmd101_thread.start()
    csv_thread.start()
    display_thread.start()

    try:
        bmd101_thread.join()
        csv_thread.join()
        display_thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        bmd101_thread.join()
        csv_thread.join()
        display_thread.join()
        print("Stopped all threads.")

if __name__ == "__main__":
    main()