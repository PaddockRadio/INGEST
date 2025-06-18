import os

def enforce_storage_limits(target_folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(target_folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
    total_gb = total_size / (1024**3)
    if total_gb > 8:
        print(f"[!] Folder size exceeds 8GB: {total_gb:.2f} GB")
    else:
        print(f"[+] Current folder usage for {target_folder}: {total_gb:.2f} GB (OK)")
