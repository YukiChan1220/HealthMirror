import threading
import csv
from queue import Queue
import global_vars
import time
from io import StringIO

class DataLogger():
    def __init__(self, config: dict) -> None:
        self.config = config
        self.file_path = config["log_path"]
        self.data_queue = config["data_queue"]
        self.lock = threading.Lock()
        self.batch_size = config.get("batch_size", 100)  # Default batch size
        self.flush_interval = config.get("flush_interval", 1.0)  # Seconds
        self.last_flush_time = time.time()
        self.buffer = []
        with open(self.file_path, 'w'):
            pass

    # log data to a CSV file in batches
    def data_log(self) -> None:
        # Collect data from queue without holding the file lock
        batch_data = []
        while not self.data_queue.empty() and len(batch_data) < self.batch_size:
            try:
                data = self.data_queue.get(block=False)
                batch_data.append(data)
                self.data_queue.task_done()
            except:
                break
        
        if not batch_data:
            return
            
        # Append to internal buffer
        self.buffer.extend(batch_data)
        
        # Determine if we should flush based on buffer size or time
        current_time = time.time()
        should_flush = (len(self.buffer) >= self.batch_size or 
                        (current_time - self.last_flush_time) >= self.flush_interval)
        
        if should_flush:
            self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        if not self.buffer:
            return
            
        # Use StringIO for in-memory buffer before writing to disk
        output = StringIO()
        writer = csv.writer(output)
        writer.writerows(self.buffer)
        
        # Only lock when actually writing to file
        with self.lock:
            with open(self.file_path, 'a', newline='', buffering=8192) as csvfile:
                csvfile.write(output.getvalue())
        
        self.buffer = []
        self.last_flush_time = time.time()

    def __call__(self) -> None:
        try:
            while global_vars.pipeline_running or not self.data_queue.empty():
                self.data_log()
                # Small sleep to prevent CPU thrashing if queue is empty
                if self.data_queue.empty():
                    time.sleep(0.01)
        finally:
            # Ensure remaining data is written when thread exits
            if self.buffer:
                self._flush_buffer()
