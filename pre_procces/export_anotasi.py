import cv2
import os
from pathlib import Path
from shutil import copy2

# Konfigurasi path
dataset = Path("dataset")
img_dir = dataset / "images"
label_dir = dataset / "labels"
classes_dir = dataset / "classes"
classes_dir.mkdir(exist_ok=True)

# Daftar nama kelas sesuai class ID
class_names = ["ch", "do", "fe", "gb", "ob", "pl", "po", "st", "ta", "ve"]

# Warna untuk setiap kelas
colors = [
    (255, 0, 0),      # ch - merah
    (0, 255, 0),      # do - hijau
    (0, 0, 255),      # fe - biru
    (255, 255, 0),    # gb - kuning
    (255, 0, 255),    # ob - magenta
    (0, 255, 255),    # pl - cyan
    (128, 0, 128),    # po - ungu tua
    (128, 128, 0),    # st - coklat muda
    (0, 128, 128),    # ta - teal
    (128, 0, 0)       # ve - maroon
]

# Buat folder tiap kelas
for cls in class_names:
    (classes_dir / cls).mkdir(exist_ok=True)

# Iterasi semua gambar
for img_path in img_dir.glob("*"):
    if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        continue

    label_path = label_dir / f"{img_path.stem}.txt"
    if not label_path.exists():
        print(f"Label not found for {img_path.name}")
        continue

    # Baca gambar
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"Failed to load image: {img_path.name}")
        continue

    h, w = img.shape[:2]

    # Baca semua label
    all_labels = []
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                cid = int(parts[0])
                xc, yc, ww, hh = map(float, parts[1:5])
                all_labels.append((cid, xc, yc, ww, hh))
            except ValueError:
                continue

    # Untuk setiap kelas, buat salinan gambar dengan hanya bounding box kelas itu
    for cls_id in range(len(class_names)):
        cls_name = class_names[cls_id]
        color = colors[cls_id]

        # Buat salinan gambar
        img_copy = img.copy()

        # Gambar hanya bounding box untuk kelas ini
        drawn_any = False
        for cid, xc, yc, ww, hh in all_labels:
            if cid == cls_id:  # hanya gambar objek dari kelas ini
                x1 = int((xc - ww/2) * w)
                y1 = int((yc - hh/2) * h)
                x2 = int((xc + ww/2) * w)
                y2 = int((yc + hh/2) * h)

                cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img_copy, cls_name, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                drawn_any = True

        # Simpan jika ada objek kelas ini
        if drawn_any:
            dest_path = classes_dir / cls_name / img_path.name
            cv2.imwrite(str(dest_path), img_copy)

print("Done! Each class folder contains images with bounding boxes of that class only.")