
import os
import cv2
import random
import shutil
from pathlib import Path
from tqdm import tqdm
import numpy as np

# ==== KONFIGURASI ====
random.seed(42)
resize_target = (640, 640)

# Lokasi dataset asli
base_dir = Path("dataset")
train_img_dir = base_dir / "train" / "images"
train_lbl_dir = base_dir / "train" / "labels"

# Folder output augmentasi (di luar folder 'train')
bright_dir = base_dir / "images_bright"
blur_dir = base_dir / "images_blur"

for d in [bright_dir / "images", bright_dir / "labels", blur_dir / "images", blur_dir / "labels"]:
    d.mkdir(parents=True, exist_ok=True)

# ==== FUNGSI AUGMENTASI MANUAL ====
def adjust_brightness(img, factor=1.2):
    """Rumus manual brightness: pixel = pixel * factor"""
    img = np.clip(img.astype(np.float32) * factor, 0, 255)
    return img.astype(np.uint8)

def motion_blur(img, kernel_size=9):
    """Rumus manual motion blur horizontal"""
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
    kernel = kernel / kernel_size
    return cv2.filter2D(img, -1, kernel)

# ==== PROSES AUGMENTASI ====
images = list(train_img_dir.glob(".jpg")) + list(train_img_dir.glob(".png"))
print(f"📸 Total gambar di train: {len(images)}")
print("🧩 Akan di-augmentasi: 100% dari gambar (semuanya)")

for img_path in tqdm(images, desc="Augmentasi berjalan"):
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"⚠ Gagal membaca {img_path}")
        continue

    # Resize ke target
    img_resized = cv2.resize(img, resize_target)
    base_name = img_path.stem

    # === Brightness Manual ===
    factor = random.uniform(0.6, 1.4)  # variasi brightness realistis
    bright_img = adjust_brightness(img_resized, factor=factor)
    cv2.imwrite(str(bright_dir / "images" / f"{base_name}_bright.jpg"), bright_img)

    lbl_path = train_lbl_dir / f"{base_name}.txt"
    if lbl_path.exists():
        shutil.copy(lbl_path, bright_dir / "labels" / f"{base_name}_bright.txt")

    # === Motion Blur Manual ===
    k_size = random.choice([5, 7, 9, 11])  # variasi ukuran blur
    blur_img = motion_blur(img_resized, kernel_size=k_size)
    cv2.imwrite(str(blur_dir / "images" / f"{base_name}_blur.jpg"), blur_img)

    if lbl_path.exists():
        shutil.copy(lbl_path, blur_dir / "labels" / f"{base_name}_blur.txt")

print("\n✅ Augmentasi manual 100% selesai!")
print(f"📂 Hasil disimpan di:")
print(f"   🔸 {bright_dir}/images dan labels (brightness)")
print(f"   🔸 {blur_dir}/images dan labels (motion blur)")