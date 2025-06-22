import cv2
import keyboard
import queue
import threading
import numpy as np
from tqdm import tqdm
import time
import signal
import sys
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, TextBox, RadioButtons
from PIL import Image
import global_vars
from capture.camera import CameraCapture
from model.physnet import PhysNet
from model.step import Step
from preprocess.mp import MediaPipePreprocess
from display.log_only import LogOnly
from utils.hr import get_average_heartrate_from_csv_file

matplotlib.use("TkAgg")


def sigint_handler(event, frame):
    global_vars.user_interrupt = True
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


class Pipeline:
    def __init__(self, config: dict) -> None:
        self.config = config
        # Whether to log info
        self.log = config["log"]
        # Capture Class
        self.capture = config["capture"]
        # Preprocess Class
        self.preprocess = config["preprocess"]
        # Model Class
        self.model = config["model"]
        # Display Class
        self.display = config["display"]
        # A hotkey string like "esc"
        self.interrupt_hotkey = config["interrupt_hotkey"]
        # User Interrupt Flag
        global_vars.user_interrupt = False
        # A queue to store the captured batched frames
        self.frame_queue = queue.Queue(maxsize=config["max_queue_size"])
        # A queue to store the preprocessed batched frames
        self.preprocess_queue = queue.Queue(maxsize=config["max_queue_size"])
        # A queue to store the predicted results
        self.result_queue = queue.Queue(maxsize=config["max_queue_size"])
        # A queue to receive the results forwarded by the Display
        self.main_queue = queue.Queue(maxsize=config["max_queue_size"])
        # A queue to receive the results forwarded by the Preprocess, e.g., MediaPipe Face Mesh image
        self.side_queue = queue.Queue(maxsize=config["max_queue_size"])
        # A list to store the results
        self.inference_results = []
        # Maximum number of points to be displayed
        self.max_display_points = config["max_display_points"]
        # The present frame to be displayed
        self.present_frame = None
        self.time_limit = config["time_limit"]
        self.threads = []
        self.hr = None
        if self.log:
            print(f"Pipeline initialized")

    def user_interrupt_handler(self) -> None:
        """
        This function is to be called when the user presses the hotkey,
        to pause or unpause the pipeline.
        :return: None
        """
        global_vars.user_interrupt = not global_vars.user_interrupt

    def monitor(self) -> None:
        pbar1 = tqdm(total=self.config["max_queue_size"], desc="Frame Queue", position=0)
        pbar2 = tqdm(total=self.config["max_queue_size"], desc="Preprocess Queue", position=1)
        pbar3 = tqdm(total=self.config["max_queue_size"], desc="Result Queue", position=2)
        while not global_vars.user_interrupt:
            pbar1.n = self.frame_queue.qsize()
            pbar2.n = self.preprocess_queue.qsize()
            pbar3.n = self.result_queue.qsize()
            pbar1.refresh()
            pbar2.refresh()
            pbar3.refresh()
            time.sleep(0.1)

    def preview(self) -> None:
        while not global_vars.user_interrupt:
            self.present_frame = self.side_queue.get()

    def results(self) -> None:
        while not global_vars.user_interrupt:
            self.inference_results.extend(self.main_queue.get())
            self.inference_results = self.inference_results[-self.max_display_points:]

    def __call__(self, monitor: bool = False, preview: bool = False, results: bool = False) -> None:
        """
        This function is the main function of the pipeline.
        :param monitor: Whether to monitor the queues.
        :param preview: Whether to preview the preprocessed frames.
        :return: None
        """
        # Register keyboard event
        keyboard.add_hotkey(self.interrupt_hotkey, self.user_interrupt_handler)
        # Initialize queues
        self.clear()
        # Start threads
        self.threads = [
            capture_thread := threading.Thread(
                target=self.capture,
                args=(self.frame_queue,),
                daemon=True,
            ),
            preprocess_thread := threading.Thread(
                target=self.preprocess,
                args=(self.frame_queue, self.preprocess_queue, self.side_queue, self.config["batch_size"]),
                daemon=True,
            ),
            model_thread := threading.Thread(
                target=self.model,
                args=(self.preprocess_queue, self.result_queue,),
                daemon=True,
            ),
            display_thread := threading.Thread(
                target=self.display,
                args=(self.result_queue, self.main_queue),
                daemon=True,
            ),
        ]
        if monitor:
            self.threads.append(monitor_thread := threading.Thread(target=self.monitor, daemon=True))
        if preview:
            self.threads.append(preview_thread := threading.Thread(target=self.preview, daemon=True))
        if results:
            self.threads.append(results_thread := threading.Thread(target=self.results, daemon=True))
        for thread in self.threads:
            thread.start()

    def clear(self):
        for thread in self.threads:
            thread.join()
        self.threads = []
        while not self.frame_queue.empty():
            self.frame_queue.get()
        while not self.preprocess_queue.empty():
            self.preprocess_queue.get()
        while not self.result_queue.empty():
            self.result_queue.get()
        while not self.main_queue.empty():
            self.frame_queue.get()
        while not self.side_queue.empty():
            self.preprocess_queue.get()
        self.present_frame = None
        self.inference_results = []
        self.hr = None

    def get_hr_async(self):
        def inner():
            self.hr = get_average_heartrate_from_csv_file(self.config["log_path"], self.config["fps"])
        threading.Thread(target=inner, daemon=True).start()


def main():
    capture_device_index, model_choice, log_path, time_limit = 0, "Step", "./log.csv", 60

    plt.axis("off")
    text_box_0_ax = plt.axes((0.3, 0.8, 0.05, 0.05))
    text_box_0 = TextBox(text_box_0_ax, "Capture Device Index ", initial="0")
    rax_1_ax = plt.axes((0.3, 0.65, 0.15, 0.1))
    rax_1 = RadioButtons(rax_1_ax, ["Step", "PhysNet"], active=0)
    text_box_2_ax = plt.axes((0.3, 0.55, 0.2, 0.05))
    text_box_2 = TextBox(text_box_2_ax, "Log Path ", initial="./log.csv")
    text_box_3_ax = plt.axes((0.3, 0.45, 0.05, 0.05))
    text_box_3 = TextBox(text_box_3_ax, "Time Limit ", initial="60")

    confirm_button_ax = plt.axes((0.3, 0.3, 0.15, 0.1))
    confirm_button = Button(confirm_button_ax, "Confirm")

    def on_confirm_button_clicked(event):
        nonlocal capture_device_index, model_choice, log_path, time_limit
        capture_device_index = int(text_box_0.text)
        model_choice = rax_1.value_selected
        log_path = text_box_2.text
        time_limit = int(text_box_3.text)
        plt.close()
    confirm_button.on_clicked(on_confirm_button_clicked)
    plt.show()

    print("Loading Camera...")
    cap = cv2.VideoCapture(capture_device_index)
    capture = CameraCapture(cap)
    print("Loading Camera...Done")
    target_size = 36 if model_choice == "Step" else 32
    batch_size = 1 if model_choice == "Step" else 128
    print("Loading MediaPipe...")
    preprocess = MediaPipePreprocess({
        "target_size": (target_size, target_size),
        "mesh_display": False,
    })
    print("Loading MediaPipe...Done")
    if model_choice == "Step":
        print("Loading Step...")
        model = Step(
            model_path="./model/models/onnx/step.onnx",
            state_path="./model/models/onnx/state.pkl",
            dt=1 / 30
        )
    else:
        print("Loading PhysNet...")
        model = PhysNet(
            model_path="./model/models/onnx/physnet.onnx"
        )
    print("Loading Model...Done")
    display = LogOnly(log_path)
    print("Loading Pipeline...")
    pipeline = Pipeline({
        "log": True,
        "capture": capture,
        "preprocess": preprocess,
        "model": model,
        "display": display,
        "interrupt_hotkey": "esc",
        "max_queue_size": 128,
        "batch_size": batch_size,
        "max_display_points": 512,
        "time_limit": time_limit,
        "log_path": log_path,
        "fps": 30,
    })
    print("Loading Pipeline...Done")
    plt_x = list(range(512))
    plt_y = np.full((512,), 0.0, dtype=np.float32)
    fig, ax = plt.subplots(1, 2, figsize=(18, 9))
    img = ax[0].imshow(np.zeros((480, 640, 3), dtype=np.uint8))
    line = ax[1].plot(plt_x, plt_y)[0]
    ax[1].set_ylim(-3.0, 3.0)
    ax[0].axis("off")
    ax[0].set_title("Camera Preview")
    ax[1].set_xlabel("Time")
    ax[1].set_ylabel("BVP value")
    ax[1].set_title("BVP value over time")
    ax[1].set_xticks([])
    record_time_base = time.time()  # Useless value, to eliminate warnings

    button_record_ax = plt.axes((0.4, 0.01, 0.08, 0.05))
    button_record = Button(button_record_ax, "Start Recording")

    def on_clicked_record(event):
        nonlocal record_time_base
        if button_record.label.get_text() == "Start Recording":
            button_record.label.set_text("Stop Recording")
            global_vars.save_result_on = True
            record_time_base = time.time()
        else:
            button_record.label.set_text("Start Recording")
            global_vars.save_result_on = False
    button_record.on_clicked(on_clicked_record)

    button_clear_ax = plt.axes((0.1, 0.01, 0.08, 0.05))
    button_clear = Button(button_clear_ax, "Start Pipeline")

    def on_clicked_clear(event):
        if button_clear.label.get_text() == "Start Pipeline":
            button_clear.label.set_text("Stop Pipeline")
            global_vars.user_interrupt = False
            pipeline(monitor=True, preview=True, results=True)
        else:
            button_clear.label.set_text("Start Pipeline")
            global_vars.user_interrupt = True
            global_vars.save_result_on = False
            button_record.label.set_text("Start Recording")
            pipeline.clear()
    button_clear.on_clicked(on_clicked_clear)

    def update_plt(frame):
        nonlocal plt_y
        if global_vars.save_result_on and time_limit is not None:
            now = time.time()
            if now - record_time_base >= time_limit:
                global_vars.save_result_on = False
                text = ax[0].text(2, 12, "OK", zorder=3)
                button_record.label.set_text("Start Recording")
                pipeline.get_hr_async()
            else:
                text = ax[0].text(2, 12, str(int(time_limit - (now - record_time_base))) + "s", zorder=3)
        elif pipeline.hr is not None:
            text = ax[0].text(2, 12, "HR: " + str(pipeline.hr), zorder=3)
        else:
            text = ax[0].text(2, 12, "Press Start Recording to begin countdown", zorder=3)
        if not global_vars.user_interrupt:
            length = len(pipeline.inference_results)
            plt_y[:length] = pipeline.inference_results
            if pipeline.present_frame is not None:
                img.set_array(Image.fromarray(pipeline.present_frame))
            line.set_ydata(plt_y)
        return img, line, text
    print("Starting GUI...")
    ani = FuncAnimation(fig, update_plt, interval=10, blit=True)
    plt.show()
    print("Exiting GUI...")
    print("Cleaning...")
    cap.release()
    global_vars.user_interrupt = True
    print("The program should be terminated now!")


if __name__ == "__main__":
    main()
