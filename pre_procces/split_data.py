import os
import random
import shutil
from pathlib import Path

# (Opsional) agar hasil random tetap sama setiap kali dijalankan
random.seed(42)

# Lokasi dataset utama (sebelum dibagi)
base_dir = Path("dataset")
train_img_dir = base_dir / "train" / "images"
train_lbl_dir = base_dir / "train" / "labels"

# Folder tujuan (valid dan test)
val_img_dir = base_dir / "valid" / "images"
val_lbl_dir = base_dir / "valid" / "labels"
test_img_dir = base_dir / "test" / "images"
test_lbl_dir = base_dir / "test" / "labels"

# Pastikan semua folder sudah ada
for d in [val_img_dir, val_lbl_dir, test_img_dir, test_lbl_dir]:
    d.mkdir(parents=True, exist_ok=True)

# Ambil semua gambar (jpg dan png)
images = list(train_img_dir.glob(".jpg")) + list(train_img_dir.glob(".png"))
random.shuffle(images)

# Hitung jumlah file untuk setiap subset
n_total = len(images)
n_val = int(n_total * 0.20)   # 20% untuk validasi
n_test = int(n_total * 0.10)  # 10% untuk testing
n_train_keep = n_total - n_val - n_test  # sisanya 70% tetap di train

print(f"Total gambar ditemukan: {n_total}")
print(f"Target split -> Train: {n_train_keep}, Val: {n_val}, Test: {n_test}")

# Pindahkan 20% ke VALID
for img_path in images[:n_val]:
    lbl_path = train_lbl_dir / f"{img_path.stem}.txt"
    shutil.move(str(img_path), str(val_img_dir / img_path.name))
    if lbl_path.exists():
        shutil.move(str(lbl_path), str(val_lbl_dir / lbl_path.name))

# Pindahkan 10% ke TEST
for img_path in images[n_val:n_val + n_test]:
    lbl_path = train_lbl_dir / f"{img_path.stem}.txt"
    shutil.move(str(img_path), str(test_img_dir / img_path.name))
    if lbl_path.exists():
        shutil.move(str(lbl_path), str(test_lbl_dir / lbl_path.name))

print(" Split selesai!")
print(f"Train: ~{n_train_keep} gambar")
print(f"Valid: {n_val} gambar")
print(f"Test:  {n_test} gambar")