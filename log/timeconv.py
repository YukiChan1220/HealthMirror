import csv
import os
import pandas as pd
import numpy as np

class TimestampConverter:
    """时间戳转换工具，将系统时间戳转换为基准时间戳"""
    
    def __init__(self, time_offset):
        """
        初始化时间戳转换器
        
        Args:
            time_offset (float): 时间偏移量（基准时间戳 - 系统时间戳）
        """
        self.time_offset = time_offset
        print(f"[TimestampConverter] Initialized with time offset: {time_offset}")
    
    def convert_csv_file(self, file_path, output_path=None):
        """
        转换CSV文件中的时间戳
        
        Args:
            file_path (str): 输入文件路径
            output_path (str): 输出文件路径，如果为None则覆盖原文件
        """
        if not os.path.exists(file_path):
            print(f"[TimestampConverter] File not found: {file_path}")
            return False
        
        if output_path is None:
            output_path = file_path
        
        try:
            # 检查文件是否为空
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"[TimestampConverter] File is empty: {file_path}")
                return True
            
            converted_rows = []
            row_count = 0
            
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 1:
                        # 跳过空行
                        continue
                    
                    try:
                        # 第一列应该是时间戳
                        original_timestamp = float(row[0])
                        converted_timestamp = original_timestamp + self.time_offset
                        
                        # 创建新行，替换第一列的时间戳
                        new_row = [converted_timestamp] + row[1:]
                        converted_rows.append(new_row)
                        row_count += 1
                        
                    except (ValueError, IndexError) as e:
                        print(f"[TimestampConverter] Error processing row in {file_path}: {row}, error: {e}")
                        # 对于无法处理的行，保持原样
                        converted_rows.append(row)
                        continue
            
            # 写入转换后的数据
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(converted_rows)
            
            print(f"[TimestampConverter] Converted {row_count} timestamps in {file_path}")
            return True
            
        except Exception as e:
            print(f"[TimestampConverter] Error converting file {file_path}: {e}")
            return False
    
    def convert_ts_file(self, file_path, output_path=None):
        # TS文件以逗号分隔，第二列是时间戳，第一行是标题
        """
        转换TS文件中的时间戳
        Args:
            file_path (str): 输入文件路径
            output_path (str): 输出文件路径，如果为None则覆盖原文件
        """
        if not os.path.exists(file_path):
            print(f"[TimestampConverter] File not found: {file_path}")
            return False
        if output_path is None:
            output_path = file_path
        try:
            df = pd.read_csv(file_path)
            if 'ts' not in df.columns:
                print(f"[TimestampConverter] 'ts' column not found in {file_path}")
                return False
            df['ts'] = df['ts'] + self.time_offset
            df.to_csv(output_path, index=False)
            print(f"[TimestampConverter] Converted timestamps in {file_path}")
            return True
        except Exception as e:
            print(f"[TimestampConverter] Error converting file {file_path}: {e}")
            return False

    def convert_session_files(self, session_dir):
        """
        转换会话目录中的所有日志文件的时间戳
        
        Args:
            session_dir (str): 会话目录路径
        """
        if not os.path.exists(session_dir):
            print(f"[TimestampConverter] Session directory not found: {session_dir}")
            return False
        
        # 需要转换的文件列表
        files_to_convert = [
            "ecg_log.csv",
            "rppg_log.csv", 
            "log.csv",
            "merged_log.csv"
        ]
        ts_files_to_convert = [
            "video.ts",
            "ir_video.ts"
        ]

        
        success_count = 0
        total_count = 0
        
        for filename in files_to_convert:
            file_path = os.path.join(session_dir, filename)
            if os.path.exists(file_path):
                total_count += 1
                if self.convert_csv_file(file_path):
                    success_count += 1
                    print(f"[TimestampConverter] Successfully converted {filename}")
                else:
                    print(f"[TimestampConverter] Failed to convert {filename}")
            else:
                print(f"[TimestampConverter] File not found: {filename}")
        
        for filename in ts_files_to_convert:
            file_path = os.path.join(session_dir, filename)
            if os.path.exists(file_path):
                total_count += 1
                if self.convert_ts_file(file_path):
                    success_count += 1
                    print(f"[TimestampConverter] Successfully converted {filename}")
                else:
                    print(f"[TimestampConverter] Failed to convert {filename}")
            else:
                print(f"[TimestampConverter] File not found: {filename}")
        
        # 特殊处理：转换PictureLogger保存的timestamps.txt文件
        self._convert_image_timestamps(session_dir)
        
        print(f"[TimestampConverter] Session conversion complete: {success_count}/{total_count} files converted successfully")
        return success_count == total_count
    
    def _convert_image_timestamps(self, session_dir):
        """转换图像时间戳文件"""
        images_dir = os.path.join(session_dir, "images")
        ir_images_dir = os.path.join(session_dir, "ir_images")
        
        for img_dir in [images_dir, ir_images_dir]:
            if os.path.exists(img_dir):
                timestamp_file = os.path.join(img_dir, "timestamps.txt")
                if os.path.exists(timestamp_file):
                    # 注意：timestamps.txt是ffmpeg格式，不是纯CSV，所以这里暂时跳过
                    # 如果需要的话，可以在这里添加特殊处理逻辑
                    print(f"[TimestampConverter] Skipping ffmpeg timestamp file: {timestamp_file}")
    
    def verify_conversion(self, file_path, sample_size=5):
        """
        验证转换结果
        
        Args:
            file_path (str): 文件路径
            sample_size (int): 采样验证的行数
        """
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            if len(rows) == 0:
                print(f"[TimestampConverter] Verification: File is empty")
                return True
            
            # 采样验证
            sample_indices = np.linspace(0, len(rows)-1, min(sample_size, len(rows)), dtype=int)
            
            print(f"[TimestampConverter] Verification sample from {file_path}:")
            for i in sample_indices:
                if len(rows[i]) > 0:
                    try:
                        timestamp = float(rows[i][0])
                        print(f"  Row {i}: timestamp = {timestamp}")
                    except ValueError:
                        print(f"  Row {i}: invalid timestamp = {rows[i][0]}")
            
            return True
            
        except Exception as e:
            print(f"[TimestampConverter] Verification error for {file_path}: {e}")
            return False
