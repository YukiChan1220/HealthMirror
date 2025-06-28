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
from model.physnet import PhysNet
from model.step import Step
from preprocess.mp import MediaPipePreprocess
from ecg.ecg import ECG
from log.dlog import DataLogger
from log.plog import PictureLogger
from log.merge import FileMerger
from log.normalize import Normalizer
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

class SessionManager:
    """管理会话数据的类"""
    def __init__(self, base_data_dir="./data"):
        self.base_data_dir = base_data_dir
        self.current_session_dir = None
        self.current_patient_id = None
        self.patient_info = None
        self.patient_id_file = os.path.join(self.base_data_dir, "patient_id_counter.txt")
        
        # 确保基础数据目录存在
        os.makedirs(self.base_data_dir, exist_ok=True)
    
    def reset_session(self):
        """重置当前会话状态"""
        self.current_session_dir = None
        self.current_patient_id = None
        self.patient_info = None
        print("[SessionManager] Session state reset")
        
    def _get_next_patient_id(self):
        """获取下一个病人ID"""
        try:
            # 尝试从文件读取当前计数器
            if os.path.exists(self.patient_id_file):
                with open(self.patient_id_file, 'r') as f:
                    current_id = int(f.read().strip())
            else:
                # 如果文件不存在，从现有目录中推断最大ID
                current_id = self._scan_existing_patient_dirs()
            
            # 递增ID
            next_id = current_id + 1
            
            # 保存新的计数器值
            with open(self.patient_id_file, 'w') as f:
                f.write(str(next_id))
            
            return next_id
            
        except Exception as e:
            print(f"[SessionManager] Error getting next patient ID: {e}")
            # 如果出错，从现有目录扫描
            return self._scan_existing_patient_dirs() + 1
    
    def _scan_existing_patient_dirs(self):
        """扫描现有的patient目录，找到最大的ID"""
        max_id = 0
        try:
            if os.path.exists(self.base_data_dir):
                for dirname in os.listdir(self.base_data_dir):
                    if dirname.startswith("patient_") and os.path.isdir(os.path.join(self.base_data_dir, dirname)):
                        try:
                            # 提取ID部分
                            id_str = dirname.replace("patient_", "")
                            patient_id = int(id_str)
                            max_id = max(max_id, patient_id)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"[SessionManager] Error scanning existing patient directories: {e}")
        
        return max_id
        
    def create_new_session(self, patient_info=None):
        """创建新的会话目录"""
        # 先重置之前的会话状态
        self.reset_session()
        
        # 获取下一个病人ID
        patient_id = self._get_next_patient_id()
        patient_id_str = f"{patient_id:06d}"  # 格式化为6位数字，如000001
        
        # 创建会话目录
        session_dir = os.path.join(self.base_data_dir, f"patient_{patient_id_str}")
        os.makedirs(session_dir, exist_ok=True)
        
        # 创建子目录
        os.makedirs(os.path.join(session_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(session_dir, "ir_images"), exist_ok=True)
        
        self.current_session_dir = session_dir
        self.current_patient_id = patient_id_str
        self.patient_info = patient_info
        
        # 保存患者信息
        timestamp = datetime.now()
        if patient_info:
            self._save_patient_info(patient_info, timestamp)
        
        print(f"[SessionManager] Created new session: {session_dir}")
        return session_dir
    
    def _save_patient_info(self, patient_info, timestamp):
        """保存患者信息到txt文件"""
        info_file = os.path.join(self.current_session_dir, "patient_info.txt")
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"Patient ID: {self.current_patient_id}\n")
            f.write(f"Session Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Patient Info: {json.dumps(patient_info, indent=2, ensure_ascii=False)}\n")
    
    def get_session_paths(self):
        """获取当前会话的各种文件路径"""
        if not self.current_session_dir:
            return {}
        
        # 确保会话目录和子目录存在
        os.makedirs(self.current_session_dir, exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.current_session_dir, "ir_images"), exist_ok=True)
        
        return {
            "session_dir": self.current_session_dir,
            "video_path": os.path.join(self.current_session_dir, "video.mp4"),
            "ir_video_path": os.path.join(self.current_session_dir, "ir_video.mp4"),
            "images_dir": os.path.join(self.current_session_dir, "images"),
            "ir_images_dir": os.path.join(self.current_session_dir, "ir_images"),
            "ecg_log": os.path.join(self.current_session_dir, "ecg_log.csv"),
            "rppg_log": os.path.join(self.current_session_dir, "rppg_log.csv"),
            "merged_log": os.path.join(self.current_session_dir, "merged_log.csv"),
            "normalized_log": os.path.join(self.current_session_dir, "normalized_log.csv"),
            "main_log": os.path.join(self.current_session_dir, "log.csv"),
        }
    
    def get_total_sessions(self):
        """获取总会话数"""
        if not os.path.exists(self.base_data_dir):
            return 0
        
        session_dirs = [d for d in os.listdir(self.base_data_dir) 
                       if d.startswith("patient_") and os.path.isdir(os.path.join(self.base_data_dir, d))]
        return len(session_dirs)
    
    def get_total_space_used(self):
        """计算已使用的存储空间（MB）"""
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
        
        return total_size / (1024 * 1024)  # 转换为MB
    
    def get_current_patient_id(self):
        """获取当前病人ID"""
        return self.current_patient_id
    
    def get_current_session_dir(self):
        """获取当前会话目录"""
        return self.current_session_dir


class BluetoothHandler:
    def __init__(self, pipeline=None, perip_manager=None):
        self.pipeline = pipeline
        self.perip_manager = perip_manager
        self.bluetooth = Bluetooth()
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        
        # Device status
        self.device_id = 1
        self.session_manager = SessionManager()
        
        # Server uploader
        self.server_uploader = ServerUploader()
        
        # Thread management
        self.handler_thread = None
        self.running = False
        
        # 添加当前会话跟踪
        self.current_upload_session = None

        self.wifi_manager = WiFiManager()

    def start(self):
        """Start the bluetooth service and command handler thread"""
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
        """Stop the bluetooth service"""
        self.running = False
        global_vars.bluetooth_running = False
        
        if self.handler_thread:
            self.handler_thread.join(timeout=2)
        
        print("[BluetoothHandler] Bluetooth handler stopped")

    def _send_ack(self, command_name, status="success"):
        """Send acknowledgment message"""
        self.tx_queue.put({
            "ack": {
                "command": command_name,
                "status": status
            }
        })

    def _handle_set_time(self, payload):
        """Handle set_time command"""
        print(f"[BluetoothHandler] Set time: {payload.get('time')}")
        return "success"

    def _handle_start_capture(self, payload):
        """Handle start_capture command"""
        patient_info = payload.get("patient_info")
        timestamp = payload.get("time")
        print(f"[BluetoothHandler] Start capture: patient={patient_info}, time={timestamp}")
        
        try:
            # 重置当前会话跟踪
            self.current_upload_session = None
            
            # 创建新的会话目录
            session_dir = self.session_manager.create_new_session(patient_info)
            
            # 更新当前会话跟踪
            self.current_upload_session = session_dir
            print(f"[BluetoothHandler] Current upload session set to: {session_dir}")
            
            if self.pipeline:
                # 更新pipeline的文件路径
                self.pipeline.update_session_paths(self.session_manager.get_session_paths())
                self.pipeline.start()
            
            return "success"
        except Exception as e:
            print(f"[BluetoothHandler] Error starting capture: {e}")
            return "failure"

    def _handle_stop_capture(self, payload):
        """Handle stop_capture command"""
        timestamp = payload.get("time")
        print(f"[BluetoothHandler] Stop capture at time {timestamp}")
        
        # 获取当前会话目录
        current_session_dir = self.current_upload_session or self.session_manager.get_current_session_dir()
        print(f"[BluetoothHandler] Current session directory for upload: {current_session_dir}")
        
        try:
            if self.pipeline:
                self.pipeline.stop()
        except Exception as e:
            print(f"[BluetoothHandler] Error stopping pipeline: {e}")
            import traceback
            traceback.print_exc()
        
        # 在停止后尝试上传数据和处理待上传的文件夹
        if current_session_dir:
            print(f"[BluetoothHandler] Starting upload process for session: {current_session_dir}")
            # 在后台线程中执行上传，避免阻塞蓝牙响应
            upload_thread = threading.Thread(
                target=self._upload_session_and_pending,
                args=(current_session_dir,),
                daemon=True,
                name="UploadThread"
            )
            upload_thread.start()
        else:
            # 即使没有当前会话，也检查是否有待上传的文件夹
            print(f"[BluetoothHandler] No current session, checking for pending uploads")
            upload_thread = threading.Thread(
                target=self._upload_pending_only,
                daemon=True,
                name="UploadPendingThread"
            )
            upload_thread.start()
        
        # 重置当前会话跟踪
        self.current_upload_session = None
        
        return "success"
    
    def _upload_session_and_pending(self, session_dir):
        """上传当前会话数据和所有待上传的文件夹"""
        try:
            print(f"[Upload] Starting upload process for: {session_dir}")
            
            # 等待一小段时间确保文件完全写入
            time.sleep(2)
            
            # 检查会话目录是否存在
            if not os.path.exists(session_dir):
                print(f"[Upload] Session directory does not exist: {session_dir}")
                return
            
            # 列出会话目录中的文件用于调试
            try:
                files_in_session = os.listdir(session_dir)
                print(f"[Upload] Files in session directory: {files_in_session}")
            except Exception as e:
                print(f"[Upload] Error listing session files: {e}")
            
            # 首先尝试上传当前会话数据
            print(f"[Upload] Attempting to upload current session data...")
            current_success = self.server_uploader.upload_patient_data(session_dir)
            if current_success:
                print(f"[Upload] Successfully uploaded current session: {session_dir}")
            else:
                print(f"[Upload] Failed to upload current session (marked as pending): {session_dir}")
            
            # 然后尝试上传所有待上传的文件夹
            print(f"[Upload] Checking for pending uploads...")
            base_data_dir = self.session_manager.base_data_dir
            batch_success, success_count, failed_count = self.server_uploader.upload_all_pending(base_data_dir)
            
            if success_count > 0:
                print(f"[Upload] Successfully uploaded {success_count} pending folders")
            if failed_count > 0:
                print(f"[Upload] Failed to upload {failed_count} pending folders")
            
            # 总结上传结果
            total_attempted = 1 + success_count + failed_count  # 当前会话 + 待上传文件夹
            total_successful = (1 if current_success else 0) + success_count
            print(f"[Upload] Upload summary: {total_successful}/{total_attempted} folders uploaded successfully")
                
        except Exception as e:
            print(f"[Upload] Error during upload: {e}")
            import traceback
            traceback.print_exc()
    
    def _upload_pending_only(self):
        """只上传待上传的文件夹"""
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
        
        # Send info after a short delay to allow for data collection
        threading.Timer(0.5, self._send_info).start()
        return "success"

    def _send_info(self):
        """Send device information with real data from peripherals"""
        try:
            # 获取电池电量
            battery_level = 70  # 默认值
            if self.perip_manager:
                try:
                    battery_level = self.perip_manager.get_battery_level()
                    if battery_level < 0:  # 如果获取失败，使用默认值
                        battery_level = 70
                except Exception as e:
                    print(f"[BluetoothHandler] Error getting battery level: {e}")
                    battery_level = 70
            
            # 获取剩余空间（假设总空间为4096MB）
            total_space = 4096
            used_space = self.session_manager.get_total_space_used()
            space_remaining = max(0, total_space - used_space)
            
            # 获取已采集病人数量
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
            # 发送默认信息以确保通信不中断
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
        
        # Use WiFiManager to handle the connection
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
                msg = self.rx_queue.get(timeout=1)
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
                continue
            except Exception as e:
                print(f"[BluetoothHandler] Exception: {e}")

    def set_pipeline(self, pipeline):
        """Set the pipeline reference"""
        self.pipeline = pipeline

    def get_session_manager(self):
        """获取会话管理器"""
        return self.session_manager


class Pipeline:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.capture = config["capture"]
        self.preprocess = config["preprocess"]
        self.ir_preprocess = config["ir_preprocess"]
        self.model = config["model"]
        self.ecg = config["ecg"]
        self.interrupt_hotkey = config["interrupt_hotkey"]
        self.log = config["log"]
        self.perip_manager = config["perip_manager"]
        self.frame_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.ir_frame_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.preprocess_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.result_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.log_result_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.main_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.log_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.ir_log_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.raw_ecg_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.display_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.filtered_ecg_queue = queue.Queue(maxsize=config["max_queue_size"])
        self.inference_results = []
        self.max_display_points = config["max_display_points"]
        self.time_limit = config["time_limit"]
        self.threads = []
        self.hr = None
        self.csv_file = config["log_path"]
        global_vars.pipeline_running = False
        self.heart_rate_buffer = []
        # 添加显示相关属性
        self.last_display_update = 0
        self.display_update_interval = 2.0  # 每2秒更新一次显示

        # 初始化日志记录器（默认路径，会在启动时更新）
        self.ecglogger = DataLogger({
            "log_path": "./ecg_log.csv",
            "data_queue": self.raw_ecg_queue,
        })
        self.rppglogger = DataLogger({
            "log_path": "./rppg_log.csv",
            "data_queue": self.log_result_queue,
        })
        self.filemerger = FileMerger(input_files=["./ecg_log.csv", "./rppg_log.csv"], output_path="merged_log.csv")

        self.picturelogger = PictureLogger({
            "video_path": "./video.mp4",
            "data_queue": self.log_queue,
            "image_path": "./images"
        })

        self.irpicturelogger = PictureLogger({
            "video_path": "./ir_video.mp4",
            "data_queue": self.ir_log_queue,
            "image_path": "./ir_images"
        })

        self.normalizer = Normalizer(rawpath="merged_log.csv", outpath="normalized_log.csv")

        # Initialize the heart rate buffer for the sliding window (10 seconds)
        self.heart_rate_buffer = []

        # Open CSV file in append mode and write header if it's empty
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['timestamp', 'inference_result'])  # Write header

        if self.log:
            print(f"[Pipeline] Pipeline initialized")

    def update_session_paths(self, session_paths):
        """更新会话路径"""
        # 确保所有目录存在
        for path_key in ["session_dir", "images_dir", "ir_images_dir"]:
            if path_key in session_paths:
                os.makedirs(session_paths[path_key], exist_ok=True)
        
        # 更新CSV文件路径
        self.csv_file = session_paths["main_log"]
        
        # 确保CSV文件的目录存在
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        
        # 重新创建CSV文件和写入头部
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['timestamp', 'inference_result'])

        # 更新各个日志记录器的路径
        # 确保日志文件的目录存在
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
            input_files=[session_paths["ecg_log"], session_paths["rppg_log"]], 
            output_path=session_paths["merged_log"]
        )

        # 确保视频文件的目录存在
        for video_path in [session_paths["video_path"], session_paths["ir_video_path"]]:
            os.makedirs(os.path.dirname(video_path), exist_ok=True)

        self.picturelogger = PictureLogger({
            "video_path": session_paths["video_path"],
            "data_queue": self.log_queue,
            "image_path": session_paths["images_dir"]
        })

        self.irpicturelogger = PictureLogger({
            "video_path": session_paths["ir_video_path"],
            "data_queue": self.ir_log_queue,
            "image_path": session_paths["ir_images_dir"]
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
            except:
                continue
            for result, timestamp in zip(results, timestamps):
                main_queue.put([timestamp, result])

    def results(self) -> None:
        while global_vars.pipeline_running:
            try:
                result = self.main_queue.get(timeout=0.5)
            except:
                print("[Pipeline] No results in the queue, waiting...")
                continue
            self.log_result_queue.put(result)
            
            # result格式是[timestamp, inference_result]
            if len(result) >= 2:
                timestamp, inference_result = result[0], result[1]
                
                # 只添加推理结果，不添加时间戳
                self.inference_results.append(inference_result)
                
                # 保持缓冲区大小限制
                if len(self.inference_results) > self.max_display_points:
                    self.inference_results.pop(0)
                
                # 使用推理结果作为心率数据
                new_heart_rate = inference_result  # 使用推理结果而不是result[0]
                self.heart_rate_buffer.append(new_heart_rate)
            
            # Ensure we only keep enough data for 10 seconds (e.g., 300 data points if fps = 30)
            if len(self.heart_rate_buffer) > self.config["fps"] * 6:
                self.heart_rate_buffer.pop(0)  # Remove the oldest value

            # Calculate heart rate when there is enough data (10 seconds worth)
            if len(self.heart_rate_buffer) >= self.config["fps"] * 6:
                # Apply the bandpass filter
                filtered_data = bandpass_filter(np.array(self.heart_rate_buffer), lowcut=0.5, highcut=3)
                # Get the heart rate from the filtered data
                heart_rate = get_hr(filtered_data)
                self.hr = heart_rate
                
                # 更新显示 - 添加这部分代码
                current_time = time.time()
                if current_time - self.last_display_update >= self.display_update_interval:
                    self.update_heart_rate_display(heart_rate)
                    self.last_display_update = current_time

    def update_heart_rate_display(self, heart_rate):
        """更新心率显示到外设管理器"""
        try:
            if self.perip_manager and heart_rate is not None:
                # 确保心率在合理范围内
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
        global_vars.pipeline_running = True
        self.last_display_update = 0
        self.threads = [
            capture_thread := threading.Thread(
                target=self.capture,
                args=(self.frame_queue, self.ir_frame_queue),
                daemon=True,
                name="CaptureThread",
            ),
            preprocess_thread := threading.Thread(
                target=self.preprocess,
                args=(self.frame_queue, self.preprocess_queue, self.log_queue, self.config["batch_size"]),
                daemon=True,
                name="PreprocessThread",
            ),
            ir_preprocess_thread := threading.Thread(
                target=self.ir_preprocess,
                args=(self.ir_frame_queue, None, self.ir_log_queue, self.config["batch_size"]),
                daemon=True,
                name="IRPreprocessThread",
            ),
            model_thread := threading.Thread(
                target=self.model,
                args=(self.preprocess_queue, self.result_queue),
                daemon=True,
                name="ModelThread",
            ),
            data_thread := threading.Thread(
                target=self.exchange_data,
                args=(self.result_queue, self.main_queue),
                daemon=True,
                name="DataExchangeThread",
            ),
            ecg_thread := threading.Thread(
                target=self.ecg,
                args=(self.raw_ecg_queue, self.filtered_ecg_queue),
                daemon=True,
                name="ECGThread",
            ),
        ]

        self.threads.append(results_thread := threading.Thread(target=self.results, daemon=True, name="ResultsThread"))
        self.threads.append(ecg_log_thread := threading.Thread(target=self.ecglogger, daemon=True, name="ECGLogThread"))
        self.threads.append(rppg_log_thread := threading.Thread(target=self.rppglogger, daemon=True, name="RPPGLogThread"))
        self.threads.append(picture_log_thread := threading.Thread(target=self.picturelogger, daemon=True, name="PictureLogThread"))
        self.threads.append(ir_picture_log_thread := threading.Thread(target=self.irpicturelogger, daemon=True, name="IRPictureLogThread"))
        for thread in self.threads:
            thread.start()
        print("[Pipeline] Pipeline started")

    def stop(self) -> None:
        global_vars.pipeline_running = False
        try:
            if self.perip_manager:
                self.perip_manager.refresh_display(0)
                print("[Pipeline] Display cleared")
        except Exception as e:
            print(f"[Pipeline] Error clearing display: {e}")
        time.sleep(1)
        self.filemerger()
        self.normalizer()
        time.sleep(1)
        self.clear()
        print("[Pipeline] Pipeline stopped")

    def clear(self):
        for thread in self.threads:
            try:
                thread.join(timeout=1)  # Add a reasonable timeout
                print(f"[Pipeline] Thread {thread.name} joined successfully")
            except Exception as e:
                print(f"[Pipeline] Error joining thread: {e}")
        # Dictionary of all queues for systematic clearing
        queues = {
            "frame_queue": self.frame_queue,
            "ir_frame_queue": self.ir_frame_queue,  # 添加缺失的队列
            "preprocess_queue": self.preprocess_queue,
            "result_queue": self.result_queue,
            "main_queue": self.main_queue,
            "log_queue": self.log_queue,
            "ir_log_queue": self.ir_log_queue,  # 添加缺失的队列
            "log_result_queue": self.log_result_queue,
            "raw_ecg_queue": self.raw_ecg_queue,
            "display_queue": self.display_queue,
            "filtered_ecg_queue": self.filtered_ecg_queue
        }
        
        # Clear all queues safely
        for name, q in queues.items():
            try:
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            except Exception as e:
                print(f"[Pipeline] Error clearing {name}: {e}")
        
        # Reset object state
        self.inference_results = []
        self.hr = None
        self.heart_rate_buffer = []  # Also clear the heart rate buffer
        
        collected = gc.collect()
        print(f"[Pipeline] Garbage collector collected {collected} objects")

        print("[Pipeline] Pipeline resources cleared")


def main():
    model_choice, log_path, time_limit = "Step", "./log.csv", 60
    rgb_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._RGB_CAMERA_SN0008-video-index0'
    ir_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera_SN0001-video-index0'

    print("[Main] RGB Camera:", rgb_cam)
    print("[Main] IR Camera", ir_cam)
    print("[Main] Model Choice:", model_choice)
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
    print("[Main] Loading Camera...Done")
    target_size = 36 if model_choice == "Step" else 32
    batch_size = 1 if model_choice == "Step" else 128
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
    if model_choice == "Step":
        model = Step(
            model_path="./model/models/onnx/step.onnx",
            state_path="./model/models/onnx/state.pkl",
            dt=1 / 30
        )
    else:
        model = PhysNet(
            model_path="./model/models/onnx/physnet.onnx"
        )
    print("[Main] Loading Model...Done")
    print("[Main] Loading Pipeline...")
    pipeline = Pipeline({
        "capture": capture,
        "preprocess": preprocess,
        "ir_preprocess": ir_preprocess,
        "model": model,
        "ecg": ecg,
        "interrupt_hotkey": "esc",
        "max_queue_size": 512,
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
    bluetooth_handler.start()
    print("[Main] Loading Bluetooth...Done")

    print("[Main] System is now waiting for Bluetooth commands (start_capture / stop_capture)...")
    try:
        while True:
            if global_vars.pipeline_running:
                if pipeline.inference_results:
                    print("[Main] Latest Inference Results:", pipeline.inference_results[-5:])
                else:
                    print("[Main] No inference results yet.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Main] Shutting down...")

    print("[Main] Releasing resources...")
    bluetooth_handler.stop()
    cap.release()


if __name__ == "__main__":
    main()
