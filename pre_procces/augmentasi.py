import os
import cv2
import random
import shutil
from pathlib import Path
from tqdm import tqdm
import numpy as np

# ==== KONFIGURASI ====
random.seed(42)

base_dir = Path("dataset")
train_img_dir = base_dir / "train" / "images"
train_lbl_prototype = base_dir / "train" / "labels"

bright_dir = base_dir / "images_bright"
blur_dir = base_dir / "images_blur"

for d in [bright_dir / "images", bright_dir / "labels", blur_dir / "images", blur_dir / "labels"]:
    d.mkdir(parents=True, exist_ok=True)

# ==== FUNGSI BRIGHTNESS ====
def adjust_brightness(img, k=30):
    img = img.astype(np.int16) + k
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)

# ==== FUNGSI MOTION BLUR ====
def motion_blur_fast(img, kernel_size=9):
    """Menghasilkan blur identik dengan motion_blur_manual, tapi lebih cepat."""
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    center = kernel_size // 2
    kernel[center, :] = 1.0 / kernel_size  # horizontal motion blur
    # Gunakan filter2D — hasilnya numerik identik dengan konvolusi manual
    return cv2.filter2D(img, -1, kernel)

# ==== PROSES AUGMENTASI ====
extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp"]
images = []
for ext in extensions:
    images.extend(train_img_dir.glob(ext))

print(f"Total gambar di {train_img_dir}: {len(images)}")
if len(images) == 0:
    print("Tidak ada gambar ditemukan! Periksa folder dan ekstensi.")
else:
    print("Akan di-augmentasi: 100% dari gambar (semuanya)")

    for img_path in tqdm(images, desc="Augmentasi berjalan"):
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Gagal membaca: {img_path}")
            continue

        img_original = img
        base_name = img_path.stem

        # === Brightness (+k) ===
        k = random.randint(-50, 50)
        bright_img = adjust_brightness(img_original, k=k)
        cv2.imwrite(str(bright_dir / "images" / f"{base_name}_bright.jpg"), bright_img)

        # === Salin label ===
        lbl_path = train_lbl_prototype / f"{base_name}.txt"
        if lbl_path.exists():
            shutil.copy(lbl_path, bright_dir / "labels" / f"{base_name}_bright.txt")

        # === Motion Blur (CEPAT, tapi KERNEL IDENTIK) ===
        k_size = random.choice([5, 7, 9, 11])
        blur_img = motion_blur_fast(img_original, kernel_size=k_size)  # ← diganti
        cv2.imwrite(str(blur_dir / "images" / f"{base_name}_blur.jpg"), blur_img)

        if lbl_path.exists():
            shutil.copy(lbl_path, blur_dir / "labels" / f"{base_name}_blur.txt")

    print("\nAugmentasi selesai! (Hasil identik, lebih cepat)")
    print(f"   Brightness: {bright_dir}/images")
    print(f"   Motion Blur: {blur_dir}/images")