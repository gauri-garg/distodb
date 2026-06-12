import os
import shutil
import time
from node.storage import Storage

def benchmark_json_read():
    bench_dir = "data/benchmark"
    if os.path.exists(bench_dir):
        shutil.rmtree(bench_dir)
    os.makedirs(bench_dir, exist_ok=True)

    # 1. Benchmark at standard milestones: 1k, 10k, 50k
    milestones = [1000, 10000, 50000]
    results = {}

    print("=========================================================")
    print("Running JSON Read Performance Benchmark...")
    print("=========================================================")

    for count in milestones:
        # Clear directory to ensure no contamination
        if os.path.exists(bench_dir):
            shutil.rmtree(bench_dir)
        os.makedirs(bench_dir, exist_ok=True)

        # Create table and insert rows
        db = Storage(data_dir=bench_dir)
        schema = {"id": "INT", "name": "TEXT", "active": "BOOL"}
        db.create_table("test", schema, "id")
        
        # Batch insert to memory directly to avoid slow disk writes during setup
        rows = []
        for i in range(count):
            rows.append({"id": i, "name": f"User_{i}_with_some_longer_text_to_make_it_realistic", "active": i % 2 == 0})
        db.tables["test"]["rows"] = rows
        db._save_table("test")

        # Measure JSON read/load time (constructor load)
        start_time = time.perf_counter()
        db_new = Storage(data_dir=bench_dir)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        results[count] = elapsed_ms
        print(f"Dataset Size: {count:<6} rows | Load Time: {elapsed_ms:.2f} ms")

    print("=========================================================")
    print("Locating the 50ms JSON read/load threshold...")
    print("=========================================================")

    # 2. Search for the 50ms threshold (Linear search in steps of 5,000 rows starting from 50k)
    # If 50k already exceeds 50ms, start lower (e.g., from 10k).
    # If 50k is below 50ms, go higher (up to 200k).
    
    # Let's dynamically decide starting point based on 50k elapsed time
    if results[50000] > 50.0:
        start_search = 10000
        step = 5000
    else:
        start_search = 50000
        step = 10000

    threshold_rows = None
    threshold_time = None
    current_count = start_search

    # Limit search to 250k rows max to prevent infinite runs
    while current_count <= 250000:
        if os.path.exists(bench_dir):
            shutil.rmtree(bench_dir)
        os.makedirs(bench_dir, exist_ok=True)

        db = Storage(data_dir=bench_dir)
        schema = {"id": "INT", "name": "TEXT", "active": "BOOL"}
        db.create_table("test", schema, "id")
        
        rows = [{"id": i, "name": f"User_{i}_with_some_longer_text_to_make_it_realistic", "active": i % 2 == 0} for i in range(current_count)]
        db.tables["test"]["rows"] = rows
        db._save_table("test")

        start_time = time.perf_counter()
        db_new = Storage(data_dir=bench_dir)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        print(f"Testing {current_count:<6} rows | Load Time: {elapsed_ms:.2f} ms")
        
        if elapsed_ms >= 50.0:
            threshold_rows = current_count
            threshold_time = elapsed_ms
            break
            
        current_count += step

    print("=========================================================")
    print("BENCHMARK REPORT")
    print("=========================================================")
    for count, elapsed_ms in results.items():
        print(f" - {count:<5} rows: {elapsed_ms:.2f} ms")
    if threshold_rows:
        print(f"\n=> 50ms Read Threshold crossed at approximately: {threshold_rows:,} rows ({threshold_time:.2f} ms)")
    else:
        print("\n=> 50ms Read Threshold was not crossed within 250,000 rows.")
    print("=========================================================")

    # Clean up benchmark files
    if os.path.exists(bench_dir):
        shutil.rmtree(bench_dir)

if __name__ == "__main__":
    benchmark_json_read()
