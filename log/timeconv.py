import os
import pandas as pd

class TimestampConverter:
    def __init__(self, time_offset):
        self.time_offset = time_offset
        print(f"[TimestampConverter] Initialized with time offset: {time_offset}")
    
    def convert_csv_file(self, file_path, output_path=None):
        if not os.path.exists(file_path):
            print(f"[TimestampConverter] File not found: {file_path}")
            return False
        
        if output_path is None:
            output_path = file_path
        
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"[TimestampConverter] File is empty: {file_path}")
                return True
            df = pd.read_csv(file_path)
            if df.empty:
                print(f"[TimestampConverter] File is empty: {file_path}")
                return True

            columns = list(df.columns)
            if not columns:
                print(f"[TimestampConverter] No columns found in {file_path}")
                return False

            try:
                df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors="coerce") + self.time_offset
            except Exception as e:
                print(f"[TimestampConverter] Error adjusting timestamps in {file_path}: {e}")
                return False

            df.to_csv(output_path, index=False)
            print(f"[TimestampConverter] Converted {len(df)} timestamps in {file_path}")
            return True
            
        except Exception as e:
            print(f"[TimestampConverter] Error converting file {file_path}: {e}")
            return False
    
    def convert_ts_file(self, file_path, output_path=None):
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
            print(f"[TimestampConverter] Converted {len(df)} timestamps in {file_path}")
            return True
        except Exception as e:
            print(f"[TimestampConverter] Error converting file {file_path}: {e}")
            return False

    def convert_session_files(self, session_dir):
        if not os.path.exists(session_dir):
            print(f"[TimestampConverter] Session directory not found: {session_dir}")
            return False
        
        files_to_convert = [
            "ecg_log.csv",
            "ppg_log.csv",
        ]
        ts_files_to_convert = [
            "video.avi.ts",
            "ir_video.avi.ts"
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
        
        self._convert_image_timestamps(session_dir)
        
        print(f"[TimestampConverter] Session conversion complete: {success_count}/{total_count} files converted successfully")
        return success_count == total_count
    
    def _convert_image_timestamps(self, session_dir):
        images_dir = os.path.join(session_dir, "images")
        ir_images_dir = os.path.join(session_dir, "ir_images")
        
        for img_dir in [images_dir, ir_images_dir]:
            if os.path.exists(img_dir):
                timestamp_file = os.path.join(img_dir, "timestamps.txt")
                if os.path.exists(timestamp_file):
                    print(f"[TimestampConverter] Skipping ffmpeg timestamp file: {timestamp_file}")
    
    def verify_conversion(self, file_path, sample_size=5):
        if not os.path.exists(file_path):
            return False
        
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                print(f"[TimestampConverter] Verification: File is empty")
                return True
            sample_indices = pd.Series(range(len(df))).sample(
                n=min(sample_size, len(df)),
                random_state=0
            ).sort_values()

            print(f"[TimestampConverter] Verification sample from {file_path}:")
            first_column = df.columns[0]
            for idx in sample_indices:
                value = df.iloc[idx, 0]
                print(f"  Row {idx}: {first_column} = {value}")
            
            return True
            
        except Exception as e:
            print(f"[TimestampConverter] Verification error for {file_path}: {e}")
            return False
