import cv2
import os
import numpy as np
from pathlib import Path
from tqdm import tqdm

# Folder input/output
input_folder = Path("dataset/images")
output_folder = Path("dataset/preprocessed-images")
output_folder.mkdir(parents=True, exist_ok=True)

# ============================
# 1. Gaussian Blur Manual Kernel
# ============================
def gaussian_blur_manual(img):
    # Kernel Gaussian 3x3
    kernel = np.array([
        [1, 2, 1],
        [2, 4, 2],
        [1, 2, 1]
    ], dtype=np.float32)

    kernel = kernel / np.sum(kernel)  # Normalisasi kernel

    # Manual convolution
    pad = 1
    img_padded = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode='reflect')
    result = np.zeros_like(img)

    for y in range(img.shape[0]):
        for x in range(img.shape[1]):
            region = img_padded[y:y+3, x:x+3]
            result[y, x] = np.sum(region * kernel[:, :, None], axis=(0, 1))

    return result

# ============================
# 2. Normalisasi Manual 0–255
# ============================
def normalize_manual(img):
    img_float = img.astype(np.float32)

    min_val = np.min(img_float)
    max_val = np.max(img_float)

    # min–max normalization
    norm = (img_float - min_val) / (max_val - min_val)
    norm = (norm * 255).astype(np.uint8)

    return norm


# ============================
# PREPROCESSING UTAMA
# ============================
def preprocess_image(img):

    # ---- 1. CLAHE pada channel L ----
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)

    lab_clahe = cv2.merge((l_clahe, a, b))
    img_clahe = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

    # ---- 2. Gaussian Blur (manual) ----
    img_blur = gaussian_blur_manual(img_clahe)

    # ---- 3. Normalisasi manual 0–255 ----
    img_norm = normalize_manual(img_blur)

    return img_norm


# ============================
# LOOP SEMUA GAMBAR
# ============================
def process_dataset():
    exts = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"]
    image_files = []

    for e in exts:
        image_files += list(input_folder.rglob(e))

    if len(image_files) == 0:
        print("Tidak ada gambar ditemukan.")
        return

    for img_path in tqdm(image_files, desc="Preprocessing images"):
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Tidak bisa membaca: {img_path}")
            continue

        processed = preprocess_image(img)
        cv2.imwrite(str(output_folder / img_path.name), processed)

    print("Preprocessing selesai!")


if __name__ == "__main__":
    process_dataset()
