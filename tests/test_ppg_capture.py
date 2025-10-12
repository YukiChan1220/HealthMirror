import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ppg import PPG

def bandpass_filter(data, lowcut=0.5, highcut=3, fs=150, order=4):
    b, a = butter(order, [lowcut, highcut], fs
                  =fs, btype='band')
    return filtfilt(b, a, data)

def main(duration: float = 10.0) -> None:
    poll_interval = 0.005
    sensor = PPG({"max30101": {"bus": 4}, "poll_interval": poll_interval})
    samples = []
    try:
        sensor.enable()
        time.sleep(1.0)
        start = time.time()
        while time.time() - start < duration:
            sample = sensor.read_ppg()
            if sample is not None:
                samples.append(sample)
                print(sample)
            else:
                print("No sample available, retrying...")
            time.sleep(poll_interval)
    finally:
        sensor.close()

    if not samples:
        print("No PPG samples captured")
        return

    base_time = samples[0][0]
    timestamps = [row[0] - base_time for row in samples]
    red = [row[1] for row in samples]
    ir = [row[2] for row in samples]
    green = [row[3] for row in samples]
    fs = len(samples) / duration
    red = bandpass_filter(red, fs=fs) if any(value is not None for value in red) else red
    ir = bandpass_filter(ir, fs=fs) if any(value is not None for value in ir) else ir
    green = bandpass_filter(green, fs=fs) if any(value is not None for value in green) else green

    print(f"Captured {len(samples)} samples over {duration} seconds, fs={fs:.2f} Hz")

    output_dir = Path("./tests/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_path = output_dir

    plt.figure(figsize=(10, 5))
    if any(value is not None for value in red):
        plt.plot(timestamps, red, label="Red", linewidth=1)
    plt.xlabel("Time (s)")
    plt.ylabel("PPG value")
    plt.title("MAX30101 PPG Red Capture")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figure_path.joinpath("ppg_capture_red.png"))
    plt.clf()
    if any(value is not None for value in ir):
        plt.plot(timestamps, ir, label="IR", linewidth=1)
        plt.xlabel("Time (s)")
    plt.ylabel("PPG value")
    plt.title("MAX30101 PPG IR Capture")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figure_path.joinpath("ppg_capture_ir.png"))
    plt.clf()
    if any(value is not None for value in green):
        plt.plot(timestamps, green, label="Green", linewidth=1)
        plt.xlabel("Time (s)")
    plt.ylabel("PPG value")
    plt.title("MAX30101 PPG Green Capture")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figure_path.joinpath("ppg_capture_green.png"))
    plt.clf()
    
    print(f"PPG capture plot saved to {figure_path}")


if __name__ == "__main__":
    main()
