import csv
import heapq
import os
import pandas as pd

class FileMerger:
    def __init__(self, input_files: list, output_path: str) -> None:
        self.input_files = input_files  # each element need to be ([data_name], file_path)
        # file format need to be (timestamp, value) with column name as (timestamp, data_name[0], data_name[1], ...)
        self.output_path = output_path
        self.heap = []
        self.last_values = dict()
        for data_names, _ in input_files:
            for data_name in data_names:
                self.last_values[data_name] = None    # file name
        with open(self.output_path, 'w'):
            pass

    def load_csv(self) -> None:
        print(f"[FileMerger] Starting to load CSV files...")
        for data_name, file in self.input_files:
            if not os.path.exists(file):
                print(f"[FileMerger] Warning: File does not exist: {file}")
                continue
            
            file_size = os.path.getsize(file)
            print(f"[FileMerger] Loading {file} (size: {file_size} bytes)")
            
            try:
                df = pd.read_csv(file, dtype=float)
                timestamps = df.iloc[:, 0].to_numpy()
                values = df.iloc[:, 1:].to_numpy().tolist()
                rows = [[t, v, data_name] for t, v in zip(timestamps, values)]
                row_count = len(rows)
                self.heap.extend(rows)
                print(f"[FileMerger] Loaded {row_count} rows from {file}")
            except Exception as e:
                print(f"[FileMerger] Error loading {file}: {e}")
                continue
        if self.heap:
            heapq.heapify(self.heap)
            print(f"[FileMerger] Heapify complete: {len(self.heap)}")
        else:
            print(f"[FileMerger] Warning: No valid data loaded")

    def write_csv(self) -> None:
        print(f"[FileMerger] Starting to write merged CSV...")
        
        if not self.heap:
            print(f"[FileMerger] No data to write")
            return
        
        try:
            rows = []
            while self.heap:
                timestamp, value, source = heapq.heappop(self.heap)
                for v, s in zip(value, source):
                    self.last_values[s] = v
                row = [timestamp]

                for data_name, last_value in self.last_values.items():
                    if last_value is not None:
                        row.append(last_value)
                    else:
                        row.append(0.0)
                rows.append(row)    # format: (timestamp, value1, value2, ...)

            row_count = len(rows)
            df = pd.DataFrame(rows, columns=["timestamp"] + list(self.last_values.keys()))
            df.to_csv(self.output_path, index=False)
            print(f"[FileMerger] Successfully wrote {row_count} rows to {self.output_path}")
        except Exception as e:
            print(f"[FileMerger] Error writing CSV: {e}")
            raise

    def __call__(self) -> None:
        print(f"[FileMerger] Merging files: {self.input_files}")
        print(f"[FileMerger] Output path: {self.output_path}")
        
        try:
            self.load_csv()
            self.write_csv()
            print(f"[FileMerger] Successfully merged {len(self.input_files)} files into {self.output_path}")
        except Exception as e:
            print(f"[FileMerger] Error during merge process: {e}")
            import traceback
            traceback.print_exc()
            raise
