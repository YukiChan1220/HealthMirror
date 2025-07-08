import os
import socket
import paramiko
from datetime import datetime

class ServerUploader:
    """处理服务器上传的类"""
    def __init__(self, server_config=None):
        # 默认服务器配置
        self.server_config = server_config or {
            "host": "183.173.177.195",  # 替换为实际服务器IP
            "port": 22,
            "username": "ssh_user",  # 替换为实际用户名
            "password": "thu_ssh_opi_test",  # 替换为实际密码
            "remote_path": "D:/health_mirror/",  # 修改为Linux路径格式
            "timeout": 30
        }
    
    def check_network_connection(self, host="8.8.8.8", port=53, timeout=3):
        """检查网络连接是否可用"""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error:
            return False
    
    def check_server_connection(self):
        """检查服务器连接是否可用"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.server_config["host"],
                port=self.server_config["port"],
                username=self.server_config["username"],
                password=self.server_config["password"],
                timeout=self.server_config["timeout"]
            )
            ssh.close()
            return True
        except Exception as e:
            print(f"[ServerUploader] Server connection failed: {e}")
            return False
    
    def mark_as_pending_upload(self, patient_folder_path):
        """标记文件夹为待上传状态"""
        try:
            pending_marker = os.path.join(patient_folder_path, ".pending_upload")
            with open(pending_marker, 'w') as f:
                f.write(f"Pending upload at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Server: {self.server_config['host']}\n")
                f.write(f"Reason: Network or server connection failed\n")
            print(f"[ServerUploader] Marked as pending upload: {patient_folder_path}")
            return True
        except Exception as e:
            print(f"[ServerUploader] Failed to mark as pending upload: {e}")
            return False
    
    def mark_as_uploaded(self, patient_folder_path, files_count=None, total_size=None):
        """标记文件夹为已上传状态"""
        try:
            # 移除待上传标记
            pending_marker = os.path.join(patient_folder_path, ".pending_upload")
            if os.path.exists(pending_marker):
                os.remove(pending_marker)
            
            # 创建已上传标记
            upload_marker = os.path.join(patient_folder_path, ".uploaded")
            folder_name = os.path.basename(patient_folder_path)
            remote_patient_path = self.server_config["remote_path"].rstrip('/') + '/' + folder_name
            
            with open(upload_marker, 'w') as f:
                f.write(f"Uploaded at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Server: {self.server_config['host']}\n")
                f.write(f"Remote path: {remote_patient_path}\n")
                if files_count is not None:
                    f.write(f"Files uploaded: {files_count}\n")
                if total_size is not None:
                    f.write(f"Total size: {total_size/1024/1024:.2f} MB\n")
            
            print(f"[ServerUploader] Marked as uploaded: {patient_folder_path}")
            return True
        except Exception as e:
            print(f"[ServerUploader] Failed to mark as uploaded: {e}")
            return False
    
    def is_uploaded(self, patient_folder_path):
        """检查文件夹是否已上传"""
        upload_marker = os.path.join(patient_folder_path, ".uploaded")
        return os.path.exists(upload_marker)
    
    def is_pending_upload(self, patient_folder_path):
        """检查文件夹是否为待上传状态"""
        pending_marker = os.path.join(patient_folder_path, ".pending_upload")
        return os.path.exists(pending_marker)
    
    def find_pending_upload_folders(self, base_data_dir):
        """查找所有待上传的文件夹"""
        pending_folders = []
        try:
            if not os.path.exists(base_data_dir):
                return pending_folders
            
            for dirname in os.listdir(base_data_dir):
                folder_path = os.path.join(base_data_dir, dirname)
                if (os.path.isdir(folder_path) and 
                    dirname.startswith("patient_") and 
                    self.is_pending_upload(folder_path)):
                    pending_folders.append(folder_path)
            
            if pending_folders:
                print(f"[ServerUploader] Found {len(pending_folders)} pending upload folders")
            
        except Exception as e:
            print(f"[ServerUploader] Error finding pending upload folders: {e}")
        
        return pending_folders
    
    def _create_remote_directory(self, sftp, remote_path):
        """递归创建远程目录"""
        try:
            sftp.stat(remote_path)
            print(f"[ServerUploader] Remote directory exists: {remote_path}")
        except IOError:
            # Directory doesn't exist, try to create it
            try:
                # Try to create parent directories first
                parent_dir = os.path.dirname(remote_path.rstrip('/'))
                if parent_dir and parent_dir != remote_path.rstrip('/') and parent_dir != '/':
                    self._create_remote_directory(sftp, parent_dir)
                
                sftp.mkdir(remote_path)
                print(f"[ServerUploader] Created remote directory: {remote_path}")
            except Exception as e:
                print(f"[ServerUploader] Failed to create remote directory {remote_path}: {e}")
    
    def upload_directory(self, local_path, remote_path):
        """上传整个目录到服务器"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.server_config["host"],
                port=self.server_config["port"],
                username=self.server_config["username"],
                password=self.server_config["password"],
                timeout=self.server_config["timeout"]
            )
            
            sftp = ssh.open_sftp()
            
            # 确保远程根目录存在
            self._create_remote_directory(sftp, remote_path)
            
            # 递归上传文件夹
            upload_count, error_count = self._upload_recursive(sftp, local_path, remote_path)
            
            sftp.close()
            ssh.close()
            
            print(f"[ServerUploader] Upload completed: {upload_count} files uploaded, {error_count} errors")
            return error_count == 0  # 只有在没有错误时才返回True
            
        except Exception as e:
            print(f"[ServerUploader] Upload failed: {e}")
            return False
    
    def _upload_recursive(self, sftp, local_path, remote_path):
        """递归上传文件夹内容，返回(上传成功数, 错误数)"""
        upload_count = 0
        error_count = 0
        
        try:
            items = os.listdir(local_path)
        except Exception as e:
            print(f"[ServerUploader] Failed to list local directory {local_path}: {e}")
            return 0, 1
        
        for item in items:
            # 跳过隐藏文件和标记文件
            if item.startswith('.'):
                continue
                
            local_item = os.path.join(local_path, item)
            # 使用正斜杠作为远程路径分隔符
            remote_item = remote_path.rstrip('/') + '/' + item
            
            if os.path.isfile(local_item):
                try:
                    # 检查本地文件是否存在且可读
                    if not os.path.exists(local_item):
                        print(f"[ServerUploader] Local file does not exist: {local_item}")
                        error_count += 1
                        continue
                    
                    file_size = os.path.getsize(local_item)
                    print(f"[ServerUploader] Uploading file: {item} ({file_size} bytes)")
                    
                    sftp.put(local_item, remote_item)
                    upload_count += 1
                    print(f"[ServerUploader] Successfully uploaded file: {item}")
                    
                except Exception as e:
                    print(f"[ServerUploader] Failed to upload file {item}: {e}")
                    error_count += 1
                    
            elif os.path.isdir(local_item):
                try:
                    # 创建远程子目录
                    self._create_remote_directory(sftp, remote_item)
                    
                    # 递归上传子目录
                    sub_upload, sub_error = self._upload_recursive(sftp, local_item, remote_item)
                    upload_count += sub_upload
                    error_count += sub_error
                    
                except Exception as e:
                    print(f"[ServerUploader] Failed to process directory {item}: {e}")
                    error_count += 1
        
        return upload_count, error_count
    
    def upload_patient_data(self, patient_folder_path):
        """上传患者数据文件夹"""
        if not os.path.exists(patient_folder_path):
            print(f"[ServerUploader] Patient folder not found: {patient_folder_path}")
            return False
        
        # 如果已经上传过，跳过
        if self.is_uploaded(patient_folder_path):
            print(f"[ServerUploader] Folder already uploaded, skipping: {patient_folder_path}")
            return True
        
        folder_name = os.path.basename(patient_folder_path)
        print(f"[ServerUploader] Starting upload process for {folder_name}...")
        
        # 立即检查网络连接
        print(f"[ServerUploader] Checking network connection...")
        if not self.check_network_connection():
            print(f"[ServerUploader] No network connection available, marking as pending upload")
            self.mark_as_pending_upload(patient_folder_path)
            return False
        
        # 立即检查服务器连接
        print(f"[ServerUploader] Checking server connection...")
        if not self.check_server_connection():
            print(f"[ServerUploader] Server connection not available, marking as pending upload")
            self.mark_as_pending_upload(patient_folder_path)
            return False
        
        # 网络和服务器都可用，开始上传
        remote_patient_path = self.server_config["remote_path"].rstrip('/') + '/' + folder_name
        
        print(f"[ServerUploader] Starting upload of {folder_name}...")
        print(f"[ServerUploader] Local path: {patient_folder_path}")
        print(f"[ServerUploader] Remote path: {remote_patient_path}")
        
        # 统计要上传的文件
        files_to_upload = []
        total_size = 0
        try:
            for root, dirs, files in os.walk(patient_folder_path):
                for file in files:
                    if file.startswith('.'):
                        continue
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, patient_folder_path)
                    file_size = os.path.getsize(file_path)
                    files_to_upload.append((rel_path, file_size))
                    total_size += file_size
            
            print(f"[ServerUploader] Files to upload ({len(files_to_upload)} total, {total_size/1024/1024:.2f} MB):")
            for rel_path, size in files_to_upload[:10]:  # 只显示前10个文件
                print(f"  - {rel_path} ({size/1024:.1f} KB)")
            if len(files_to_upload) > 10:
                print(f"  ... and {len(files_to_upload) - 10} more files")
                
        except Exception as e:
            print(f"[ServerUploader] Error listing files: {e}")
            files_to_upload = []
            total_size = 0
        
        # 执行上传
        success = self.upload_directory(patient_folder_path, remote_patient_path)
        
        if success:
            print(f"[ServerUploader] Successfully uploaded {folder_name}")
            self.mark_as_uploaded(patient_folder_path, len(files_to_upload), total_size)
            return True
        else:
            print(f"[ServerUploader] Failed to upload {folder_name}, marking as pending upload")
            self.mark_as_pending_upload(patient_folder_path)
            return False
    
    def upload_all_pending(self, base_data_dir):
        """上传所有待上传的文件夹"""
        print(f"[ServerUploader] Checking for pending uploads in: {base_data_dir}")
        
        # 首先检查网络和服务器连接
        if not self.check_network_connection():
            print(f"[ServerUploader] No network connection, skipping pending uploads")
            return False, 0, 0
        
        if not self.check_server_connection():
            print(f"[ServerUploader] No server connection, skipping pending uploads")
            return False, 0, 0
        
        # 查找所有待上传的文件夹
        pending_folders = self.find_pending_upload_folders(base_data_dir)
        
        if not pending_folders:
            print(f"[ServerUploader] No pending uploads found")
            return True, 0, 0
        
        print(f"[ServerUploader] Starting batch upload of {len(pending_folders)} pending folders")
        
        success_count = 0
        failed_count = 0
        
        for folder_path in pending_folders:
            folder_name = os.path.basename(folder_path)
            print(f"[ServerUploader] Uploading pending folder: {folder_name}")
            
            if self.upload_patient_data(folder_path):
                success_count += 1
                print(f"[ServerUploader] Successfully uploaded pending folder: {folder_name}")
            else:
                failed_count += 1
                print(f"[ServerUploader] Failed to upload pending folder: {folder_name}")
        
        print(f"[ServerUploader] Batch upload completed: {success_count} success, {failed_count} failed")
        return failed_count == 0, success_count, failed_count
