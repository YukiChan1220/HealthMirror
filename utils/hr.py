from scipy.signal import welch, butter, filtfilt
import numpy as np
import pandas as pd


def bandpass_filter(data, low_cut=0.5, high_cut=3, fs=30, order=3):
    b, a = butter(
        N=order,
        Wn=[low_cut, high_cut],
        fs=fs,
        btype="band"
    )  # Using Butterworth filter to filter wave frequency between 0.5, 3 Hz (30 ~ 180 BPM).
    return filtfilt(b, a, data)


def get_hr(y, sr=30, hr_min=30, hr_max=180):
    p, q = welch(y, sr, nfft=int(1e5 / sr), nperseg=np.min((len(y) - 1, 256)))
    return p[(p > hr_min / 60) & (p < hr_max / 60)][np.argmax(
        q[(p > hr_min / 60) & (p < hr_max / 60)])] * 60  # Using welch method to calculate PSD and find the peak of it.


def get_average_heartrate_from_csv_file(path: str, fps: int) -> float:
    bvps = np.array(pd.read_csv(path)["bvp"].values)
    bvps = bandpass_filter(bvps, fs=fps)
    hrs = []
    for i in range(450, len(bvps) + 10, 10):
        t = get_hr(bvps[i - 450:i], fps)
        while len(hrs) < min(i, len(bvps)) // 10:
            hrs.append(t)
    return np.mean(hrs)
