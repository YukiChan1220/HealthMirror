# coding=utf-8

import cv2
import queue
import threading
import numpy as np
import time
import os
import csv
import json
import gc
from datetime import datetime
from scipy.signal import butter, filtfilt, welch

import global_vars
from bluetooth.listen import Bluetooth
from capture.camera import CameraCapture
from preprocess.mp import MediaPipePreprocess
from ecg.ecg import ECG
from log.dlog import DataLogger
from log.plog import PictureLogger
from log.merge import FileMerger
from log.normalize import Normalizer
from log.timeconv import TimestampConverter
from peripherals.peripherals import Peripherals
from peripheralmanager.peripmanager import PeripheralManager
from network.wifi import WiFiManager
from network.uploader import ServerUploader


def bandpass_filter(data, lowcut=0.5, highcut=3, fs=30, order=3):
    b, a = butter(order, [lowcut, highcut], fs=fs, btype='band')
    return filtfilt(b, a, data)

def get_hr(y, sr=30, min=30, max=180):
    f, Pxx = welch(y, sr, nfft=1e5 / sr, nperseg=np.min((len(y) - 1, 256)))
    return f[(f > min / 60) & (f < max / 60)][np.argmax(Pxx[(f > min / 60) & (f < max / 60)])] * 60

def handle_thread_exception(args):
    pass
threading.excepthook = handle_thread_exception

class SessionManager:
    def __init__(self, base_data_dir="./data"):
        self.base_data_dir = base_data_dir
        self.current_session_dir = None
        self.current_patient_id = None
        self.patient_info = None
        self.patient_id_file = os.path.join(self.base_data_dir, "patient_id_counter.txt")
        
        self.reference_timestamp = None
        self.system_timestamp = None
        self.time_offset = None

        os.makedirs(self.base_data_dir, exist_ok=True)
    
    def reset_session(self):
        """重置当前会话状态"""
        self.current_session_dir = None
        self.current_patient_id = None
        self.patient_info = None
        self.reference_timestamp = None
        self.system_timestamp = None
        self.time_offset = None
        print("[SessionManager] Session state reset")
        
    def _get_next_patient_id(self):
        try:
            if os.path.exists(self.patient_id_file):
                with open(self.patient_id_file, 'r') as f:
                    current_id = int(f.read().strip())
            else:
                current_id = self._scan_existing_patient_dirs()
            next_id = current_id + 1
            
            with open(self.patient_id_file, 'w') as f:
                f.write(str(next_id))
            
            return next_id
            
        except Exception as e:
            print(f"[SessionManager] Error getting next patient ID: {e}")
            return self._scan_existing_patient_dirs() + 1
    
    def _scan_existing_patient_dirs(self):
        max_id = 0
        try:
            if os.path.exists(self.base_data_dir):
                for dirname in os.listdir(self.base_data_dir):
                    if dirname.startswith("patient_") and os.path.isdir(os.path.join(self.base_data_dir, dirname)):
                        try:
                            id_str = dirname.replace("patient_", "")
                            patient_id = int(id_str)
                            max_id = max(max_id, patient_id)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"[SessionManager] Error scanning existing patient directories: {e}")
        
        return max_id
        
    def set_reference_time(self, reference_timestamp):
        self.reference_timestamp = float(reference_timestamp)
        self.system_timestamp = time.time()
        self.time_offset = self.reference_timestamp - self.system_timestamp
        print(f"[SessionManager] Time sync set: reference={self.reference_timestamp}, system={self.system_timestamp}, offset={self.time_offset}")
    
    def get_time_offset(self):
        return self.time_offset
    
    def convert_system_to_reference_time(self, system_timestamp):
        if self.time_offset is None:
            print("[SessionManager] Warning: No time offset set, using original timestamp")
            return system_timestamp
        return system_timestamp + self.time_offset
        
    def create_new_session(self, patient_info=None):
        saved_reference_timestamp = self.reference_timestamp
        saved_system_timestamp = self.system_timestamp
        saved_time_offset = self.time_offset
        self.current_session_dir = None
        self.current_patient_id = None
        self.patient_info = None
        self.reference_timestamp = saved_reference_timestamp
        self.system_timestamp = saved_system_timestamp
        self.time_offset = saved_time_offset
        
        print("[SessionManager] Session state reset (time sync preserved)")
        patient_id = self._get_next_patient_id()
        patient_id_str = f"{patient_id:06d}"
        
        session_dir = os.path.join(self.base_data_dir, f"patient_{patient_id_str}")
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(session_dir, "ir_images"), exist_ok=True)
        
        self.current_session_dir = session_dir
        self.current_patient_id = patient_id_str
        self.patient_info = patient_info
        
        timestamp = datetime.now()
        if patient_info:
            self._save_patient_info(patient_info, timestamp)
        
        print(f"[SessionManager] Created new session: {session_dir}")
        if self.time_offset is not None:
            print(f"[SessionManager] Time sync preserved: offset={self.time_offset}")
        return session_dir
    
    def _save_patient_info(self, patient_info, timestamp):
        info_file = os.path.join(self.current_session_dir, "patient_info.txt")
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"Patient ID: {self.current_patient_id}\n")
            f.write(f"Session Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Patient Info: {json.dumps(patient_info, indent=2, ensure_ascii=False)}\n")
    
    def get_session_paths(self):
        if not self.current_session_dir:
            return {}
        os.makedirs(self.current_session_dir, exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "ir_images"), exist_ok=True)
        
        return {
            "session_dir": self.current_session_dir,
            "video_path": os.path.join(self.current_session_dir, "video.mkv"),
            "ir_video_path": os.path.join(self.current_session_dir, "ir_video.mkv"),
            "images_dir": os.path.join(self.current_session_dir, "images"),
            "ir_images_dir": os.path.join(self.current_session_dir, "ir_images"),
            "ecg_log": os.path.join(self.current_session_dir, "ecg_log.csv"),
            "rppg_log": os.path.join(self.current_session_dir, "rppg_log.csv"),
            "merged_log": os.path.join(self.current_session_dir, "merged_log.csv"),
            "normalized_log": os.path.join(self.current_session_dir, "normalized_log.csv"),
            "main_log": os.path.join(self.current_session_dir, "log.csv"),
        }
    
    def get_total_sessions(self):
        if not os.path.exists(self.base_data_dir):
            return 0
        session_dirs = [d for d in os.listdir(self.base_data_dir) 
                       if d.startswith("patient_") and os.path.isdir(os.path.join(self.base_data_dir, d))]
        return len(session_dirs)
    
    def get_total_space_used(self):
        if not os.path.exists(self.base_data_dir):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.base_data_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass
        
        return total_size / (1024 * 1024)
    
    def get_current_patient_id(self):
        return self.current_patient_id
    
    def get_current_session_dir(self):
        return self.current_session_dir


class BluetoothHandler:
    def __init__(self, pipeline=None, perip_manager=None):
        self.pipeline = pipeline
        self.perip_manager = perip_manager
        self.bluetooth = Bluetooth()
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        self.device_id = 1
        self.session_manager = SessionManager()
        self.server_uploader = ServerUploader()
        self.handler_thread = None
        self.running = False
        self.current_upload_session = None

        self.wifi_manager = WiFiManager()

    def start(self):
        self.bluetooth(self.tx_queue, self.rx_queue)
        global_vars.bluetooth_running = True
        self.running = True
        
        self.handler_thread = threading.Thread(
            target=self._handle_commands, 
            daemon=True, 
            name="BluetoothHandlerThread"
        )
        self.handler_thread.start()
        print("[BluetoothHandler] Bluetooth handler started")

    def stop(self):
        self.running = False
        global_vars.bluetooth_running = False
        
        if self.handler_thread:
            self.handler_thread.join(timeout=2)
        
        print("[BluetoothHandler] Bluetooth handler stopped")

    def _send_ack(self, command_name, status="success"):
        self.tx_queue.put({
            "ack": {
                "command": command_name,
                "status": status
            }
        })

    def _handle_set_time(self, payload):
        print(f"[BluetoothHandler] Set time: {payload.get('time')}")
        return "success"

    def _handle_start_capture(self, payload):
        patient_info = payload.get("patient_info")
        timestamp = payload.get("time")
        print(f"[BluetoothHandler] Start capture: patient={patient_info}, time={timestamp}")
        
        try:
            self.current_upload_session = None
            if timestamp is not None:
                self.session_manager.set_reference_time(timestamp)
            else:
                print("[BluetoothHandler] Warning: No timestamp provided in start_capture command")
            session_dir = self.session_manager.create_new_session(patient_info)
            self.current_upload_session = session_dir
            print(f"[BluetoothHandler] Current upload session set to: {session_dir}")
            
            if self.pipeline:
                self.pipeline.update_session_paths(self.session_manager.get_session_paths())
                self.pipeline.start()
            
            return "success"
        except Exception as e:
            print(f"[BluetoothHandler] Error starting capture: {e}")
            return "failure"

    def _handle_stop_capture(self, payload):
        timestamp = payload.get("time")
        print(f"[BluetoothHandler] Stop capture at time {timestamp}")
        current_session_dir = self.current_upload_session or self.session_manager.get_current_session_dir()
        print(f"[BluetoothHandler] Current session directory for upload: {current_session_dir}")
        
        try:
            if self.pipeline:
                self.pipeline.stop()
        except Exception as e:
            print(f"[BluetoothHandler] Error stopping pipeline: {e}")
            import traceback
            traceback.print_exc()
        if current_session_dir:
            print(f"[BluetoothHandler] Starting upload process for session: {current_session_dir}")
            upload_thread = threading.Thread(
                target=self._upload_session_and_pending,
                args=(current_session_dir,),
                daemon=True,
                name="UploadThread"
            )
            upload_thread.start()
        else:
            print(f"[BluetoothHandler] No current session, checking for pending uploads")
            upload_thread = threading.Thread(
                target=self._upload_pending_only,
                daemon=True,
                name="UploadPendingThread"
            )
            upload_thread.start()
        self.current_upload_session = None
        
        return "success"
    
    # upload all pending folders
    def _upload_session_and_pending(self, session_dir):
        try:
            print(f"[Upload] Starting upload process for: {session_dir}")
            time.sleep(2)
            if not os.path.exists(session_dir):
                print(f"[Upload] Session directory does not exist: {session_dir}")
                return
            try:
                files_in_session = os.listdir(session_dir)
                print(f"[Upload] Files in session directory: {files_in_session}")
            except Exception as e:
                print(f"[Upload] Error listing session files: {e}")
            print(f"[Upload] Attempting to upload current session data...")
            current_success = self.server_uploader.upload_patient_data(session_dir)
            if current_success:
                print(f"[Upload] Successfully uploaded current session: {session_dir}")
            else:
                print(f"[Upload] Failed to upload current session (marked as pending): {session_dir}")
            print(f"[Upload] Checking for pending uploads...")
            base_data_dir = self.session_manager.base_data_dir
            batch_success, success_count, failed_count = self.server_uploader.upload_all_pending(base_data_dir)
            
            if success_count > 0:
                print(f"[Upload] Successfully uploaded {success_count} pending folders")
            if failed_count > 0:
                print(f"[Upload] Failed to upload {failed_count} pending folders")
            total_attempted = 1 + success_count + failed_count
            total_successful = (1 if current_success else 0) + success_count
            print(f"[Upload] Upload summary: {total_successful}/{total_attempted} folders uploaded successfully")
                
        except Exception as e:
            print(f"[Upload] Error during upload: {e}")
            import traceback
            traceback.print_exc()

    # upload only pending folders
    def _upload_pending_only(self):
        try:
            print(f"[Upload] Checking for pending uploads only...")
            base_data_dir = self.session_manager.base_data_dir
            batch_success, success_count, failed_count = self.server_uploader.upload_all_pending(base_data_dir)
            
            if success_count > 0:
                print(f"[Upload] Successfully uploaded {success_count} pending folders")
            if failed_count > 0:
                print(f"[Upload] Failed to upload {failed_count} pending folders")
            elif success_count == 0:
                print(f"[Upload] No pending uploads found")
                
        except Exception as e:
            print(f"[Upload] Error during pending upload check: {e}")
            import traceback
            traceback.print_exc()

    def _handle_refresh_info(self, payload):
        """Handle refresh_info command"""
        timestamp = payload.get("time")
        print(f"[BluetoothHandler] Refresh info at time {timestamp}")
        threading.Timer(0.5, self._send_info).start()
        return "success"

    def _send_info(self):
        try:
            battery_level = 70
            if self.perip_manager:
                try:
                    battery_level = self.perip_manager.get_battery_level()
                    if battery_level < 0:
                        battery_level = 70
                except Exception as e:
                    print(f"[BluetoothHandler] Error getting battery level: {e}")
                    battery_level = 70
            total_space = 40960
            used_space = self.session_manager.get_total_space_used()
            space_remaining = max(0, total_space - used_space)
            patient_count = self.session_manager.get_total_sessions()
            
            info_data = {
                "info": {
                    "device_id": self.device_id,
                    "patient_count": patient_count,
                    "space_remaining": int(space_remaining),
                    "battery_level": battery_level
                }
            }
            
            print(f"[BluetoothHandler] Sending device info: {info_data}")
            self.tx_queue.put(info_data)
            
        except Exception as e:
            print(f"[BluetoothHandler] Error sending device info: {e}")
            self.tx_queue.put({
                "info": {
                    "device_id": self.device_id,
                    "patient_count": 0,
                    "space_remaining": 4096,
                    "battery_level": 70
                }
            })

    def _handle_config_wifi(self, payload):
        """Handle config_wifi command"""
        ssid = payload.get("ssid")
        auth = payload.get("auth", "OPEN")
        username = payload.get("username", "")
        password = payload.get("password", "")
        timestamp = payload.get("time")
        
        print(f"[BluetoothHandler] Config WiFi: ssid={ssid}, auth={auth}, user={username}, time={timestamp}")
        result = self.wifi_manager.connect(ssid, auth, username, password)
        
        if result["status"] == "success":
            print(f"[WiFiManager] {result['message']}")
            return "success"
        else:
            print(f"[WiFiManager] {result['message']}")
            return "failure"

    def _handle_commands(self):
        """Main command handling loop"""
        command_handlers = {
            "set_time": self._handle_set_time,
            "start_capture": self._handle_start_capture,
            "stop_capture": self._handle_stop_capture,
            "refresh_info": self._handle_refresh_info,
            "config_wifi": self._handle_config_wifi,
        }

        while self.running:
            try:
                msg = self.rx_queue.get(timeout=0.5)
                if not isinstance(msg, dict):
                    print(f"[BluetoothHandler] Ignoring invalid message: {msg}")
                    continue

                command_name = next(iter(msg))
                payload = msg[command_name]

                if command_name in command_handlers:
                    try:
                        status = command_handlers[command_name](payload)
                        self._send_ack(command_name, status)
                    except Exception as e:
                        print(f"[BluetoothHandler] Error handling {command_name}: {e}")
                        self._send_ack(command_name, "error")
                else:
                    print(f"[BluetoothHandler] Unknown command: {command_name}")
                    self._send_ack(command_name, "unknown")

            except queue.Empty:
                time.sleep(0.01)
                continue
            except Exception as e:
                print(f"[BluetoothHandler] Exception: {e}")
                time.sleep(0.1)

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        if self.pipeline:
            self.pipeline.session_manager = self.session_manager

    def get_session_manager(self):
        return self.session_manager


class Pipeline:
    def __init__(self, config: dict, session_manager=None) -> None:
        self.config = config
        self.capture = config["capture"]
        self.preprocess = config["preprocess"]
        self.ir_preprocess = config["ir_preprocess"]
        self.ecg = config["ecg"]
        self.interrupt_hotkey = config["interrupt_hotkey"]
        self.log = config["log"]
        self.perip_manager = config["perip_manager"]
        self.session_manager = session_manager
        frame_queue_size = config.get("frame_queue_size", 128)
        preprocess_queue_size = config.get("preprocess_queue_size", 128)
        log_queue_size = config.get("log_queue_size", 512)
        ecg_queue_size = config.get("ecg_queue_size", 1024)

        self.frame_queue = queue.Queue(maxsize=frame_queue_size)
        self.raw_frame_queue = queue.Queue(maxsize=frame_queue_size)
        self.ir_frame_queue = queue.Queue(maxsize=frame_queue_size)
        self.raw_ir_frame_queue = queue.Queue(maxsize=frame_queue_size)
        self.preprocess_queue = queue.Queue(maxsize=preprocess_queue_size)
        self.result_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.log_result_queue = queue.Queue(maxsize=log_queue_size)
        self.main_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.log_queue = queue.Queue(maxsize=log_queue_size)
        self.ir_log_queue = queue.Queue(maxsize=log_queue_size)
        self.log_queue1 = queue.Queue(maxsize=log_queue_size)
        self.ir_log_queue1 = queue.Queue(maxsize=log_queue_size)
        self.raw_ecg_queue = queue.Queue(maxsize=ecg_queue_size)
        self.display_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.monitor_ecg_queue = queue.Queue(maxsize=ecg_queue_size)
        self.inference_results = []
        self.max_display_points = config["max_display_points"]
        self.time_limit = config["time_limit"]
        self.threads = []
        self.hr = None
        self.csv_file = config["log_path"]
        global_vars.pipeline_running = False
        self.heart_rate_buffer = []
        
        self.cached_frames = []
        self.cached_timestamps = []
        self.cache_lock = threading.Lock()
        self.max_cached_frames = config.get("max_cached_frames", 18000)  # 限制缓存帧数（约10分钟@30fps）
        # 添加显示相关属性
        self.last_display_update = 0
        self.display_update_interval = 1.0  # 每1秒更新一次显示
        
        # 添加ECG质量监测相关属性
        self.ecg_buffer = []
        self.ecg_window_size = config.get("ecg_window_size", 1024)  # 1 sec
        self.ecg_quality = "normal"  # 初始质量状态
        self.ecg_quality_thresholds = {
            "normal": 6000,    # 极差小于5000为正常
            "warning": 8000,   # 极差5000-8000为警告
            # 极差大于8000为错误
        }
        # 在Pipeline.__init__方法中添加这些属性
        self.last_ecg_quality_display = 0
        self.ecg_quality_display_interval = 3.0  # 每3秒显示一次ECG质量信息

        # 添加心率计算相关属性
        self.heart_rate_calculation_buffer = []  # 用于心率计算的ECG数据缓冲区
        self.heart_rate_window_size = 10240  # 心率计算的窗口大小 (约10秒@512Hz)
        self.last_heart_rate_calculation = 0
        self.heart_rate_calculation_interval = 2.0  # 每2秒计算一次心率
        self.current_heart_rate = 0  # 当前计算出的心率
        self.ecg_sampling_rate = 512  # ECG采样率，假设为512Hz
        
        # 添加ECG调试信息控制标志
        self.enable_ecg_debug_output = True  # 控制ECG Range等调试信息的输出

        # 添加队列监控相关属性
        self.enable_queue_monitoring = config.get("enable_queue_monitoring", True)
        self.queue_monitor_interval = config.get("queue_monitor_interval", 3.0)  # 每5秒监控一次
        self.last_queue_monitor = 0
        
        # 添加缓存日志控制属性
        self.cache_log_interval = config.get("cache_log_interval", 3.0)  # 每10秒输出一次缓存信息
        self.last_cache_log = 0
        self.cache_frame_count = 0
        self.heart_rate_buffer = []

        # Open CSV file in append mode and write header if it's empty
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['timestamp', 'inference_result'])  # Write header

        if self.log:
            print(f"[Pipeline] Pipeline initialized")

    def update_session_paths(self, session_paths):
        for path_key in ["session_dir", "images_dir", "ir_images_dir"]:
            if path_key in session_paths:
                os.makedirs(session_paths[path_key], exist_ok=True)

        for log_path in [session_paths["ecg_log"], session_paths["rppg_log"]]:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        self.ecglogger = DataLogger({
            "log_path": session_paths["ecg_log"],
            "data_queue": self.raw_ecg_queue,
        })
        
        self.rppglogger = DataLogger({
            "log_path": session_paths["rppg_log"],
            "data_queue": self.log_result_queue,
        })
        
        self.filemerger = FileMerger(
            input_files=[session_paths["rppg_log"], session_paths["ecg_log"]], 
            output_path=session_paths["merged_log"]
        )
        for video_path in [session_paths["video_path"], session_paths["ir_video_path"]]:
            os.makedirs(os.path.dirname(video_path), exist_ok=True)

        self.picturelogger = PictureLogger({
            "video_path": session_paths["video_path"],
            "data_queue": self.log_queue,
            "image_path": session_paths["images_dir"],
            "image_type": "np"  # 使用numpy数组格式
        })

        self.irpicturelogger = PictureLogger({
            "video_path": session_paths["ir_video_path"],
            "data_queue": self.ir_log_queue,
            "image_path": session_paths["ir_images_dir"],
            "image_type": "np"  # 使用numpy数组格式
        })

        self.raw_frame_logger = PictureLogger({
            "video_path": session_paths["video_path"].replace("video.mkv", "raw_video.mkv"),
            "data_queue": self.log_queue1,
            "image_path": session_paths["images_dir"].replace("images", "raw_images"),
            "image_type": "raw"
        })

        self.raw_ir_frame_logger = PictureLogger({
            "video_path": session_paths["ir_video_path"].replace("ir_video.mkv", "raw_ir_video.mkv"),
            "data_queue": self.ir_log_queue1,
            "image_path": session_paths["ir_images_dir"].replace("ir_images", "raw_ir_images"),
            "image_type": "raw"
        })

        # 确保合并和归一化文件的目录存在
        for path in [session_paths["merged_log"], session_paths["normalized_log"]]:
            os.makedirs(os.path.dirname(path), exist_ok=True)

        self.normalizer = Normalizer(
            rawpath=session_paths["merged_log"], 
            outpath=session_paths["normalized_log"]
        )
        
        print(f"[Pipeline] Pipeline paths updated for session: {session_paths['session_dir']}")

    def exchange_data(self, result_queue: queue.Queue, main_queue: queue.Queue) -> None:
        while global_vars.pipeline_running:
            try:
                results, timestamps = result_queue.get(timeout=0.5)
                for result, timestamp in zip(results, timestamps):
                    main_queue.put([timestamp, result])
            except queue.Empty:
                # 队列为空时短暂休眠，减少CPU占用
                time.sleep(0.01)
                continue
            except Exception as e:
                print(f"[Pipeline] Error in exchange_data: {e}")
                time.sleep(0.1)

    def monitor_queue_status(self):
        if not self.enable_queue_monitoring:
            return
        current_time = time.time()
        if current_time - self.last_queue_monitor < self.queue_monitor_interval:
            return
            
        try:
            queue_status = {
                "frame_queue": self.frame_queue.qsize(),
                "ir_frame_queue": self.ir_frame_queue.qsize(),
                "preprocess_queue": self.preprocess_queue.qsize(),
                "log_queue": self.log_queue.qsize(),
                "ir_log_queue": self.ir_log_queue.qsize(),
                "raw_ecg_queue": self.raw_ecg_queue.qsize(),
                "monitor_ecg_queue": self.monitor_ecg_queue.qsize(),
                "log_result_queue": self.log_result_queue.qsize(),
            }
            
            warnings = []
            for queue_name, size in queue_status.items():
                queue_obj = getattr(self, queue_name)
                if hasattr(queue_obj, '_maxsize') and queue_obj._maxsize > 0:
                    usage_percent = (size / queue_obj._maxsize) * 100
                    if usage_percent > 80:
                        warnings.append(f"{queue_name}: {size}/{queue_obj._maxsize} ({usage_percent:.1f}%)")
            
            if warnings:
                print(f"[Pipeline] Queue warnings: {', '.join(warnings)}")
            elif self.log:
                active_queues = [f"{name}: {size}" for name, size in queue_status.items() if size > 0]
                if active_queues:
                    print(f"[Pipeline] Queue status: {', '.join(active_queues)}")
            
            self.last_queue_monitor = current_time
            
        except Exception as e:
            print(f"[Pipeline] Error monitoring queue status: {e}")

    def results(self) -> None:
        while global_vars.pipeline_running and global_vars.data_acquisition_running:
            try:
                self.monitor_queue_status()
                self._process_ecg_quality()
                current_time = time.time()
                if current_time - self.last_ecg_quality_display >= self.ecg_quality_display_interval:
                    if self.current_heart_rate > 0:
                        print(f"[Pipeline] ECG Quality: {self.ecg_quality}, Heart Rate: {self.current_heart_rate:.1f} BPM (caching mode)")
                    else:
                        print(f"[Pipeline] ECG Quality: {self.ecg_quality} (caching mode, calculating heart rate...)")
                    self.last_ecg_quality_display = current_time
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[Pipeline] Error in results processing: {e}")
                time.sleep(0.1)

    def _process_ecg_quality(self):
        try:
            while not self.monitor_ecg_queue.empty():
                try:
                    ecg_data = self.monitor_ecg_queue.get_nowait()
                    if isinstance(ecg_data, (list, tuple)) and len(ecg_data) > 1:
                        ecg_value = ecg_data[1]
                    else:
                        ecg_value = float(ecg_data)
                    self.ecg_buffer.append(ecg_value)
                    if len(self.ecg_buffer) > self.ecg_window_size:
                        self.ecg_buffer.pop(0)
                    self.heart_rate_calculation_buffer.append(ecg_value)
                    if len(self.heart_rate_calculation_buffer) > self.heart_rate_window_size:
                        self.heart_rate_calculation_buffer.pop(0)
                        
                except queue.Empty:
                    break
                except (ValueError, TypeError, IndexError) as e:
                    print(f"[Pipeline] Error processing ECG data: {e}")
                    continue
            if len(self.ecg_buffer) >= self.ecg_window_size:
                ecg_array = np.array(self.ecg_buffer)
                ecg_range = np.max(ecg_array) - np.min(ecg_array)
                if ecg_range <= self.ecg_quality_thresholds["normal"]:
                    self.ecg_quality = "normal"
                elif ecg_range <= self.ecg_quality_thresholds["warning"]:
                    self.ecg_quality = "warning"
                else:
                    self.ecg_quality = "error"
                if self.log and self.enable_ecg_debug_output:
                    print(f"[Pipeline] ECG Range: {ecg_range:.1f}, Quality: {self.ecg_quality}")
            
            # hr calculation
            current_time = time.time()
            min_data_for_calculation = int(self.ecg_sampling_rate * 2)
            data_duration = len(self.heart_rate_calculation_buffer) / self.ecg_sampling_rate
            if data_duration < 5:
                dynamic_interval = 1.0
            elif data_duration < 10:
                dynamic_interval = 1.5
            else:
                dynamic_interval = self.heart_rate_calculation_interval

            if (current_time - self.last_heart_rate_calculation >= dynamic_interval and
                len(self.heart_rate_calculation_buffer) >= min_data_for_calculation):
                self._calculate_heart_rate()
                self.last_heart_rate_calculation = current_time
                    
        except Exception as e:
            print(f"[Pipeline] Error in ECG quality processing: {e}")
            self.ecg_quality = "error"
    
    def _calculate_heart_rate(self):
        try:
            min_data_for_calculation = int(self.ecg_sampling_rate * 2)
            if len(self.heart_rate_calculation_buffer) < min_data_for_calculation:
                return
            data_length = min(len(self.heart_rate_calculation_buffer), self.heart_rate_window_size)
            ecg_data = np.array(self.heart_rate_calculation_buffer[-data_length:])
            data_duration = data_length / self.ecg_sampling_rate
            confidence_factor = min(1.0, data_duration / 20.0)
            from scipy.signal import butter, filtfilt
            nyquist = self.ecg_sampling_rate / 2
            low_cutoff = 0.5 / nyquist
            high_cutoff = 40 / nyquist
            b, a = butter(3, [low_cutoff, high_cutoff], btype='band')
            filtered_ecg = filtfilt(b, a, ecg_data)
            from scipy.signal import find_peaks
            threshold = np.std(filtered_ecg) * 1.4
            min_distance = int(self.ecg_sampling_rate * 0.3)
            peaks, _ = find_peaks(filtered_ecg, height=threshold, distance=min_distance)
            if len(peaks) >= 2:
                rr_intervals = np.diff(peaks) / self.ecg_sampling_rate
                avg_rr_interval = np.mean(rr_intervals)
                heart_rate = 60.0 / avg_rr_interval
                if 30 <= heart_rate <= 200:
                    self.current_heart_rate = heart_rate
                    self.update_heart_rate_display(heart_rate)
                    
                    if self.log:
                        confidence_info = f"confidence: {confidence_factor:.1%}" if confidence_factor < 1.0 else "full confidence"
                        print(f"[Pipeline] Calculated heart rate: {heart_rate:.1f} BPM (from {len(peaks)} peaks, {data_duration:.1f}s data, {confidence_info})")
                else:
                    if self.log:
                        print(f"[Pipeline] Heart rate out of range: {heart_rate:.1f} BPM (data: {data_duration:.1f}s)")
            else:
                if self.log:
                    print(f"[Pipeline] Insufficient R peaks detected: {len(peaks)} (data: {data_duration:.1f}s)")
                    
        except Exception as e:
            print(f"[Pipeline] Error calculating heart rate: {e}")
            if self.current_heart_rate > 0:
                self.update_heart_rate_display(self.current_heart_rate)

    def update_heart_rate_display(self, heart_rate):
        try:
            if global_vars.data_acquisition_running and self.perip_manager and heart_rate is not None:
                hr_display = max(30, min(200, int(round(heart_rate))))
                self.perip_manager.refresh_display(hr_display)
                print(f"[Pipeline] Heart rate displayed: {hr_display} BPM")
        except Exception as e:
            print(f"[Pipeline] Error updating heart rate display: {e}")

    def __call__(self, duration: int) -> None:
        if duration >= 0:
            self.start()
            if duration > 0:
                threading.Thread(target=self._delayed_stop, args=(duration,), daemon=True).start()
        else:
            self.stop()

    def _delayed_stop(self, duration: int) -> None:
        time.sleep(duration)
        self.stop()

    def start(self) -> None:
        self.clear()
        self.enable_ecg_debug_output = True
        global_vars.pipeline_running = True
        global_vars.data_acquisition_running = True
        self.last_display_update = 0
        self.threads = [
            capture_thread := threading.Thread(
                target=self.capture,
                args=(self.frame_queue, self.raw_frame_queue, self.ir_frame_queue, self.raw_ir_frame_queue),
                daemon=True,
                name="CaptureThread",
            ),
            preprocess_thread := threading.Thread(
                target=self.preprocess,
                args=(self.frame_queue, self.preprocess_queue, self.log_queue, self.log_queue1, self.config["batch_size"]),
                daemon=True,
                name="PreprocessThread",
            ),
            ir_preprocess_thread := threading.Thread(
                target=self.ir_preprocess,
                args=(self.ir_frame_queue, None, self.ir_log_queue, self.ir_log_queue1, self.config["batch_size"]),
                daemon=True,
                name="IRPreprocessThread",
            ),
            ecg_thread := threading.Thread(
                target=self.ecg,
                args=(self.raw_ecg_queue, self.monitor_ecg_queue),
                daemon=True,
                name="ECGThread",
            ),
        ]

        self.threads.append(results_thread := threading.Thread(target=self.results, daemon=True, name="ResultsThread"))
        self.threads.append(ecg_log_thread := threading.Thread(target=self.ecglogger, daemon=True, name="ECGLogThread"))
        self.threads.append(rppg_log_thread := threading.Thread(target=self.rppglogger, daemon=True, name="RPPGLogThread"))
        self.threads.append(picture_log_thread := threading.Thread(target=self.picturelogger, daemon=True, name="PictureLogThread"))
        self.threads.append(ir_picture_log_thread := threading.Thread(target=self.irpicturelogger, daemon=True, name="IRPictureLogThread"))
        self.threads.append(raw_frame_log_thread := threading.Thread(target=self.raw_frame_logger, daemon=True, name="RawPictureLogThread"))
        self.threads.append(raw_ir_frame_log_thread := threading.Thread(target=self.raw_ir_frame_logger, daemon=True, name="RawIRPictureLogThread"))
        for thread in self.threads:
            thread.start()
        print("[Pipeline] Pipeline started with caching mode")

    def stop(self) -> None:
        print("[Pipeline] Stage 1: Stopping data acquisition...")
        global_vars.data_acquisition_running = False
        try:
            if hasattr(self.capture, 'stop_capture'):
                self.capture.stop_capture()
                print("[Pipeline] Camera capture stopped")
        except Exception as e:
            print(f"[Pipeline] Error stopping camera capture: {e}")
        try:
            if hasattr(self.ecg, 'stop_capture'):
                self.ecg.stop_capture()
                print("[Pipeline] ECG capture stopped")
        except Exception as e:
            print(f"[Pipeline] Error stopping ECG capture: {e}")
        time.sleep(0.5)
        
        print("[Pipeline] Stage 2: Stopping terminal output and display refresh...")
        self.enable_ecg_debug_output = False
        try:
            if self.perip_manager:
                self.perip_manager.refresh_display(1111)
                print("[Pipeline] Display cleared")
        except Exception as e:
            print(f"[Pipeline] Error clearing display: {e}")
        try:
            if hasattr(self.capture, 'cleanup'):
                self.capture.cleanup()
                print("[Pipeline] Camera resources cleaned up")
        except Exception as e:
            print(f"[Pipeline] Error cleaning up camera: {e}")
        try:
            if hasattr(self.ecg, 'cleanup'):
                self.ecg.cleanup()
                print("[Pipeline] ECG resources cleaned up")
        except Exception as e:
            print(f"[Pipeline] Error cleaning up ECG: {e}")
        time.sleep(0.5)

        print("[Pipeline] Waiting for log queues to be processed...")
        max_wait_time = 30
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_time:
            if (self.log_result_queue.empty() and 
                self.raw_ecg_queue.empty() and 
                self.log_queue.empty() and 
                self.ir_log_queue.empty()):
                print("[Pipeline] All log queues are empty")
                break
            time.sleep(0.1)
        else:
            print(f"[Pipeline] Timeout waiting for log queues to empty after {max_wait_time}s")
        
        print("[Pipeline] Stage 4: Stopping all threads and finalizing...")
        global_vars.pipeline_running = False
        print("[Pipeline] Set pipeline_running to False, allowing all threads to exit")
        if self.session_manager and self.session_manager.get_time_offset() is not None:
            print("[Pipeline] Converting timestamps to reference time...")
            try:
                current_session_dir = self.session_manager.get_current_session_dir()
                if current_session_dir:
                    time_offset = self.session_manager.get_time_offset()
                    converter = TimestampConverter(time_offset)
                    conversion_success = converter.convert_session_files(current_session_dir)
                    if conversion_success:
                        print("[Pipeline] Timestamp conversion completed successfully")
                        if self.log:
                            print("[Pipeline] Verifying timestamp conversion...")
                            for filename in ["ecg_log.csv", "rppg_log.csv", "log.csv"]:
                                file_path = os.path.join(current_session_dir, filename)
                                if os.path.exists(file_path):
                                    converter.verify_conversion(file_path)
                    else:
                        print("[Pipeline] Warning: Some timestamp conversions failed")
                else:
                    print("[Pipeline] Warning: No current session directory for timestamp conversion")
            except Exception as e:
                print(f"[Pipeline] Error during timestamp conversion: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[Pipeline] No time offset available, skipping timestamp conversion")
        try:
            self.filemerger()
        except Exception as e:
            print(f"[Pipeline] File merge failed: {e}")
        
        try:
            self.normalizer()
        except Exception as e:
            print(f"[Pipeline] Normalization failed: {e}")
        
        time.sleep(1)
        self.clear()
        print("[Pipeline] Pipeline stopped")
        self.perip_manager.refresh_display(0)

    def clear(self):
        print("[Pipeline] Clearing queues before joining threads...")
        queues = {
            "frame_queue": self.frame_queue,
            "ir_frame_queue": self.ir_frame_queue,
            "preprocess_queue": self.preprocess_queue,
            "result_queue": self.result_queue,
            "main_queue": self.main_queue,
            "log_queue": self.log_queue,
            "ir_log_queue": self.ir_log_queue,
            "log_result_queue": self.log_result_queue,
            "raw_ecg_queue": self.raw_ecg_queue,
            "display_queue": self.display_queue,
            "monitor_ecg_queue": self.monitor_ecg_queue
        }
        for name, q in queues.items():
            try:
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            except Exception as e:
                print(f"[Pipeline] Error clearing {name}: {e}")
        
        print("[Pipeline] Queues cleared, now joining threads...")
        picture_log_threads = [thread for thread in self.threads if "PictureLogThread" in thread.name]
        capture_threads = [thread for thread in self.threads if "CaptureThread" in thread.name]
        other_threads = [thread for thread in self.threads if "PictureLogThread" not in thread.name and "CaptureThread" not in thread.name]
        for thread in other_threads:
            try:
                thread.join(timeout=2)
                if thread.is_alive():
                    print(f"[Pipeline] Warning: Thread {thread.name} did not join within timeout")
                else:
                    print(f"[Pipeline] Thread {thread.name} joined successfully")
            except Exception as e:
                print(f"[Pipeline] Error joining thread {thread.name}: {e}")
        for thread in capture_threads:
            try:
                print(f"[Pipeline] Waiting for {thread.name} to release camera resources...")
                thread.join(timeout=5)
                if thread.is_alive():
                    print(f"[Pipeline] Warning: Thread {thread.name} did not join within timeout")
                else:
                    print(f"[Pipeline] Thread {thread.name} joined successfully")
            except Exception as e:
                print(f"[Pipeline] Error joining thread {thread.name}: {e}")
        for thread in picture_log_threads:
            try:
                print(f"[Pipeline] Waiting for {thread.name} to complete video creation...")
                thread.join(timeout=10)
                if thread.is_alive():
                    print(f"[Pipeline] Warning: Thread {thread.name} did not join within timeout")
                else:
                    print(f"[Pipeline] Thread {thread.name} joined successfully")
            except Exception as e:
                print(f"[Pipeline] Error joining thread {thread.name}: {e}")
        
        self.inference_results = []
        self.hr = None
        self.heart_rate_buffer = []
        self.heart_rate_calculation_buffer = []
        self.ecg_buffer = []
        self.ecg_quality = "normal"
        self.enable_ecg_debug_output = True

        global_vars.pipeline_running = False
        global_vars.data_acquisition_running = False
        
        with self.cache_lock:
            cached_count = len(self.cached_frames)
            self.cached_frames.clear()
            self.cached_timestamps.clear()
            print(f"[Pipeline] Cleared {cached_count} cached frames and timestamps")

        self.last_display_update = 0
        self.last_ecg_quality_display = 0
        self.last_queue_monitor = 0  # 重置队列监控时间
        self.last_cache_log = 0  # 重置缓存日志时间
        self.cache_frame_count = 0  # 重置累计缓存帧数
        
        # 强制垃圾回收
        collected = gc.collect()
        print(f"[Pipeline] Garbage collector collected {collected} objects")

        print("[Pipeline] Pipeline resources cleared")


def main():
    log_path, time_limit = "./log.csv", 60
    rgb_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._RGB_CAMERA_SN0008-video-index0'
    ir_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera_SN0001-video-index0'

    print("[Main] RGB Camera:", rgb_cam)
    print("[Main] IR Camera", ir_cam)
    print("[Main] Log Path:", log_path)
    print("[Main] Time Limit:", time_limit)

    print("[Main] Loading Peripherals...")
    peripherals = Peripherals()
    ecg = ECG({
        "bmd101": {"serial_port": "/dev/ttyS0"},
        "max_queue_size": 512,
    })
    peripmanager = PeripheralManager("/dev/ttyS3")
    print("[Main] Loading Peripherals...Done")

    print("[Main] Loading Camera...")
    cap = cv2.VideoCapture(rgb_cam)
    ir_cap = cv2.VideoCapture(ir_cam)
    capture = CameraCapture(cap, ir_cap)
    
    # 设置摄像头路径，用于重新初始化
    capture.set_camera_paths(rgb_cam, ir_cam)
    
    print("[Main] Loading Camera...Done")
    #target_size = 36 if model_choice == "Step" else 32
    target_size = 128
    batch_size = 1
    print("[Main] Loading MediaPipe...")
    preprocess = MediaPipePreprocess({
        "target_size": (target_size, target_size),
        "mesh_display": False,
    })
    ir_preprocess = MediaPipePreprocess({
        "target_size": (target_size, target_size),
        "mesh_display": False,
    })
    
    print("[Main] Loading MediaPipe...Done")

    print("[Main] Loading Pipeline...")
    pipeline = Pipeline({
        "capture": capture,
        "preprocess": preprocess,
        "ir_preprocess": ir_preprocess,
        "ecg": ecg,
        "interrupt_hotkey": "esc",
        "max_queue_size": 512,
        "frame_queue_size": 256,
        "preprocess_queue_size": 256,
        "log_queue_size": 512,
        "ecg_queue_size": 1024,
        "max_cached_frames": 18000,  # 约10分钟@30fps
        "enable_queue_monitoring": True,
        "queue_monitor_interval": 5.0,
        "cache_log_interval": 10.0,  # 每10秒输出一次缓存信息
        "batch_size": batch_size,
        "max_display_points": 128,
        "time_limit": time_limit,
        "log_path": log_path,
        "fps": 30,
        "perip_manager": peripmanager,
        "log": True,
    })
    print("[Main] Loading Pipeline...Done")

    print("[Main] Loading Bluetooth...")
    bluetooth_handler = BluetoothHandler(pipeline, peripmanager)
    # 在设置pipeline后，会自动设置session_manager引用
    bluetooth_handler.set_pipeline(pipeline)
    bluetooth_handler.start()
    print("[Main] Loading Bluetooth...Done")

    print("[Main] System is now waiting for Bluetooth commands (start_capture / stop_capture)...")
    try:
        last_status = None
        while True:
            if False:
                msg = {
                    "start_capture": {
                        "patient_info": {"name": "Test Patient", "age": 30, "gender": "male"},  # 空患者信息
                        "time": time.time()  # 当前时间戳
                    }
                }
                bluetooth_handler.rx_queue.put(msg)
                print("[SIM] Sent simulated start_capture command")
                time.sleep(300)
                msg = {"stop_capture": {"time": time.time()}}
                bluetooth_handler.rx_queue.put(msg)
                print("[SIM] Sent stop_capture command")
            
            current_status = global_vars.pipeline_running
            data_acquisition_status = global_vars.data_acquisition_running
            
            if current_status != last_status:
                if current_status:
                    with pipeline.cache_lock:
                        cached_count = len(pipeline.cached_frames)
                    print(f"[Main] Caching mode active. Cached frames: {cached_count}")
                else:
                    print("[Main] Pipeline stopped, waiting for commands...")
                last_status = current_status
            elif current_status and data_acquisition_status:  # 只在数据采集阶段显示缓存状态
                with pipeline.cache_lock:
                    cached_count = len(pipeline.cached_frames)
                if cached_count > 0:  # 只在有缓存数据时显示
                    print(f"[Main] Data acquisition active. Cached frames: {cached_count}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Main] Shutting down...")

    print("[Main] Releasing resources...")
    bluetooth_handler.stop()
    
    # 释放摄像头资源
    try:
        cap.release()
        print("[Main] RGB camera released")
    except Exception as e:
        print(f"[Main] Error releasing RGB camera: {e}")
    
    try:
        ir_cap.release()
        print("[Main] IR camera released")
    except Exception as e:
        print(f"[Main] Error releasing IR camera: {e}")
    
    # 释放OpenCV资源
    try:
        cv2.destroyAllWindows()
        print("[Main] OpenCV windows destroyed")
    except Exception as e:
        print(f"[Main] Error destroying OpenCV windows: {e}")


if __name__ == "__main__":
    main()
