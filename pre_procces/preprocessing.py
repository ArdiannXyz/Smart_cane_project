import cv2
import os
from pathlib import Path
from tqdm import tqdm
import numpy as np

# Folder input & output
input_folder = Path("dataset/images")
output_folder = Path("dataset/preprocessed-images")
output_folder.mkdir(parents=True, exist_ok=True)

def preprocess_image(img):

    # ---- 1. CLAHE pada channel L (LAB) ----
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)

    lab_clahe = cv2.merge((l_clahe, a, b))
    img_clahe = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

    # ---- 2. Gaussian Blur ----
    img_blur = cv2.GaussianBlur(img_clahe, (3, 3), 0)

    # ---- 3. Normalisasi 0–255 ----
    img_norm = cv2.normalize(img_blur, None, alpha=0, beta=255,
                             norm_type=cv2.NORM_MINMAX)

    return img_norm


# ==== LOOP UNTUK SEMUA GAMBAR ====
def process_dataset():
    # Membaca berbagai format gambar
    exts = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"]
    image_files = []

    for e in exts:
        image_files += list(input_folder.rglob(e))

    if len(image_files) == 0:
        print("Tidak ada file gambar ditemukan di folder input.")

        print("❌ Tidak ada file gambar ditemukan di folder input.")
        return

    for img_path in tqdm(image_files, desc="Preprocessing images"):
        img = cv2.imread(str(img_path))

        if img is None:
            print(f"Gambar rusak atau tidak bisa dibaca: {img_path}")
            print(f"⚠ Gambar rusak atau tidak bisa dibaca: {img_path}")

            continue

        processed = preprocess_image(img)

        save_path = output_folder / img_path.name
        cv2.imwrite(str(save_path), processed)

    print("Preprocessing selesai!")


if __name__ == "__main__":
    process_dataset()
