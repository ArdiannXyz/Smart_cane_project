

import cv2
import os
from pathlib import Path
from tqdm import tqdm

# Folder dataset
input_folder = Path("dataset/images")
output_folder = Path("dataset/images-preprocessed")

# Buat folder output jika belum ada
output_folder.mkdir(exist_ok=True, parents=True)

# Target size sesuai YOLOv5n-Seg
TARGET_SIZE = 640

def preprocess_image(img):
    # Resize
    img_resized = cv2.resize(img, (TARGET_SIZE, TARGET_SIZE))

    # BGR → RGB (tidak wajib disimpan, hanya jika ingin konsisten)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

    return img_rgb


# Loop semua gambar
image_files = list(input_folder.glob("."))

print(f"Total gambar ditemukan: {len(image_files)}")

for img_path in tqdm(image_files):
    img = cv2.imread(str(img_path))

    if img is None:
        print(f"GAMBAR RUSAK: {img_path}")
        continue

    processed = preprocess_image(img)

    # Nama file output
    out_path = output_folder / img_path.name

    # Simpan (YOLO training tidak butuh normalisasi disimpan)
    cv2.imwrite(str(out_path), cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))

print("Preprocessing selesai! Hasil disimpan di folder: dataset/images-preprocessed")