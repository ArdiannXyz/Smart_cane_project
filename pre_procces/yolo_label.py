import cv2
import os
import argparse
from pathlib import Path
import glob

class YOLOv5Labeler:
    def __init__(self, dataset_path, max_width=1280, max_height=720):
        self.dataset_path = Path(dataset_path)
        self.images_dir = self.dataset_path / "images"
        self.labels_dir = self.dataset_path / "labels"
        
        # Buat direktori jika belum ada
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)
        
        # Ukuran maksimal window (bisa disesuaikan dengan resolusi layar Anda)
        self.max_display_width = max_width
        self.max_display_height = max_height
        
        # Scale factor untuk konversi koordinat display <-> original
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        # Mapping kelas ke kode YOLO
        self.classes = {
            'ch': 0,  # chair
            'do': 1,  # door
            'fe': 2,  # fence
            'gb': 3,  # garbage bin
            'ob': 4,  # obstacle
            'pl': 5,  # plant
            'po': 6,  # pothole
            'st': 7,  # stair
            'ta': 8,  # table
            've': 9   # vehicle
        }
        
        # Mapping keyboard shortcut ke kelas
        self.keyboard_mapping = {
            ord('c'): 'ch',  # chair
            ord('d'): 'do',  # door
            ord('f'): 'fe',  # fence
            ord('g'): 'gb',  # garbage bin
            ord('o'): 'ob',  # obstacle
            ord('p'): 'pl',  # plant
            ord('h'): 'po',  # pothole (h untuk hole)
            ord('s'): 'st',  # stair
            ord('t'): 'ta',  # table
            ord('v'): 've'   # vehicle
        }
        
        self.current_class = 'ch'  # Default class
        self.drawing = False
        self.ix, self.iy = -1, -1
        self.current_boxes = []
        
        # Dapatkan semua file gambar TANPA DUPLIKAT
        self.image_files = self.get_unique_image_files()
        self.current_image_index = 0
        
        print(f"Found {len(self.image_files)} unique images in {self.images_dir}")
        print(f"Display window max size: {self.max_display_width}x{self.max_display_height}")

    def get_unique_image_files(self):
        """Mendapatkan file gambar unik tanpa duplikat"""
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']
        all_files = []
        
        for ext in image_extensions:
            # Cari dengan case sensitive
            files = list(self.images_dir.glob(ext))
            all_files.extend(files)
            
            # Juga cari dengan uppercase
            files_upper = list(self.images_dir.glob(ext.upper()))
            all_files.extend(files_upper)
        
        # Hapus duplikat dengan menggunakan dictionary
        unique_files_dict = {}
        for file_path in all_files:
            unique_files_dict[file_path.name.lower()] = file_path
        
        # Konversi kembali ke list dan urutkan
        unique_files = list(unique_files_dict.values())
        unique_files.sort(key=lambda x: x.name)
        
        return unique_files

    def resize_image_for_display(self, image):
        """Resize gambar agar pas di layar sambil mempertahankan aspect ratio"""
        orig_height, orig_width = image.shape[:2]
        
        # Hitung scale factor
        scale_w = self.max_display_width / orig_width
        scale_h = self.max_display_height / orig_height
        scale = min(scale_w, scale_h, 1.0)  # max 1.0 agar tidak memperbesar gambar kecil
        
        # Simpan scale factor untuk konversi koordinat
        self.scale_x = scale
        self.scale_y = scale
        
        if scale < 1.0:
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)
            resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            print(f"Image resized from {orig_width}x{orig_height} to {new_width}x{new_height} (scale: {scale:.2f})")
            return resized
        else:
            print(f"Image size {orig_width}x{orig_height} fits display, no resize needed")
            return image.copy()
    
    def display_to_original(self, x, y):
        """Konversi koordinat dari display ke original image"""
        orig_x = int(x / self.scale_x)
        orig_y = int(y / self.scale_y)
        return orig_x, orig_y
    
    def original_to_display(self, x, y):
        """Konversi koordinat dari original image ke display"""
        disp_x = int(x * self.scale_x)
        disp_y = int(y * self.scale_y)
        return disp_x, disp_y

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.ix, self.iy = x, y
            
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                img_copy = self.display_image.copy()
                cv2.rectangle(img_copy, (self.ix, self.iy), (x, y), (0, 255, 0), 2)
                
                # Gambar semua box yang sudah ada (dalam koordinat display)
                for box in self.current_boxes:
                    x1_orig, y1_orig, x2_orig, y2_orig, class_name = box
                    x1, y1 = self.original_to_display(x1_orig, y1_orig)
                    x2, y2 = self.original_to_display(x2_orig, y2_orig)
                    
                    class_id = self.classes[class_name]
                    color = self.get_color(class_id)
                    cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(img_copy, class_name, (x1, y1-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                cv2.imshow('YOLOv5 Labeler - SmartCane', img_copy)
                
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            
            # Konversi koordinat display ke original
            x1_disp, y1_disp = min(self.ix, x), min(self.iy, y)
            x2_disp, y2_disp = max(self.ix, x), max(self.iy, y)
            
            x1_orig, y1_orig = self.display_to_original(x1_disp, y1_disp)
            x2_orig, y2_orig = self.display_to_original(x2_disp, y2_disp)
            
            # Pastikan box memiliki area yang cukup (dalam koordinat display)
            if abs(x2_disp - x1_disp) > 10 and abs(y2_disp - y1_disp) > 10:
                # Simpan dalam koordinat ORIGINAL
                self.current_boxes.append((x1_orig, y1_orig, x2_orig, y2_orig, self.current_class))
                print(f"Added {self.current_class} box (original coords): ({x1_orig}, {y1_orig}, {x2_orig}, {y2_orig})")
                
            self.redraw_image()
    
    def get_color(self, class_id):
        colors = [
            (255, 0, 0),    # ch - merah
            (0, 255, 0),    # do - hijau
            (0, 0, 255),    # fe - biru
            (255, 255, 0),  # gb - cyan
            (255, 0, 255),  # ob - magenta
            (0, 255, 255),  # pl - kuning
            (128, 0, 128),  # po - ungu
            (128, 128, 0),  # st - olive
            (0, 128, 128),  # ta - teal
            (128, 0, 0)     # ve - maroon
        ]
        return colors[class_id % len(colors)]
    
    def redraw_image(self):
        img_copy = self.display_image.copy()
        
        # Gambar semua bounding boxes (konversi dari original ke display)
        for box in self.current_boxes:
            x1_orig, y1_orig, x2_orig, y2_orig, class_name = box
            x1, y1 = self.original_to_display(x1_orig, y1_orig)
            x2, y2 = self.original_to_display(x2_orig, y2_orig)
            
            class_id = self.classes[class_name]
            color = self.get_color(class_id)
            
            cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
            cv2.putText(img_copy, f'{class_name} ({class_id})', (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Tampilkan informasi
        orig_h, orig_w = self.current_image.shape[:2]
        disp_h, disp_w = self.display_image.shape[:2]
        
        cv2.putText(img_copy, f'Current Class: {self.current_class}', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img_copy, f'Image: {self.current_image_index + 1}/{len(self.image_files)}', (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img_copy, f'Boxes: {len(self.current_boxes)}', (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img_copy, f'Original: {orig_w}x{orig_h} | Display: {disp_w}x{disp_h}', (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(img_copy, f'File: {self.image_files[self.current_image_index].name}', (10, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imshow('YOLOv5 Labeler - SmartCane', img_copy)
    
    def convert_to_yolo_format(self, x1, y1, x2, y2, img_width, img_height):
        """Konversi koordinat pixel ke format YOLO (normalized center x, center y, width, height)"""
        x_center = ((x1 + x2) / 2) / img_width
        y_center = ((y1 + y2) / 2) / img_height
        width = (x2 - x1) / img_width
        height = (y2 - y1) / img_height
        
        # Pastikan nilai dalam range [0, 1]
        x_center = max(0, min(1, x_center))
        y_center = max(0, min(1, y_center))
        width = max(0, min(1, width))
        height = max(0, min(1, height))
        
        return x_center, y_center, width, height
    
    def save_labels(self):
        if self.current_image_index >= len(self.image_files):
            return
            
        image_file = self.image_files[self.current_image_index]
        label_file = self.labels_dir / f"{image_file.stem}.txt"
        
        # Gunakan dimensi ORIGINAL image
        img_height, img_width = self.current_image.shape[:2]
        
        with open(label_file, 'w') as f:
            for box in self.current_boxes:
                x1, y1, x2, y2, class_name = box
                class_id = self.classes[class_name]
                
                x_center, y_center, width, height = self.convert_to_yolo_format(
                    x1, y1, x2, y2, img_width, img_height
                )
                
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
        
        print(f"Labels saved to: {label_file}")
    
    def load_existing_labels(self):
        if self.current_image_index >= len(self.image_files):
            return
            
        image_file = self.image_files[self.current_image_index]
        label_file = self.labels_dir / f"{image_file.stem}.txt"
        
        self.current_boxes = []
        
        if label_file.exists():
            # Gunakan dimensi ORIGINAL image
            img_height, img_width = self.current_image.shape[:2]
            
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width = float(parts[3])
                        height = float(parts[4])
                        
                        # Konversi dari YOLO format ke pixel coordinates (ORIGINAL)
                        x1 = int((x_center - width/2) * img_width)
                        y1 = int((y_center - height/2) * img_height)
                        x2 = int((x_center + width/2) * img_width)
                        y2 = int((y_center + height/2) * img_height)
                        
                        # Pastikan koordinat dalam batas gambar
                        x1 = max(0, min(img_width, x1))
                        y1 = max(0, min(img_height, y1))
                        x2 = max(0, min(img_width, x2))
                        y2 = max(0, min(img_height, y2))
                        
                        # Cari class name dari class_id
                        class_name = None
                        for name, cid in self.classes.items():
                            if cid == class_id:
                                class_name = name
                                break
                        
                        if class_name:
                            self.current_boxes.append((x1, y1, x2, y2, class_name))
            
            print(f"Loaded {len(self.current_boxes)} existing boxes from {label_file}")
    
    def show_help(self):
        help_text = [
            "\n=== YOLOv5 Labeler - SmartCane - Keyboard Shortcuts ===",
            "c - Chair (ch)", "d - Door (do)", "f - Fence (fe)", 
            "g - Garbage Bin (gb)", "o - Obstacle (ob)", "p - Plant (pl)",
            "h - Pothole (po)", "s - Stair (st)", "t - Table (ta)", 
            "v - Vehicle (ve)",
            "n - Next image", "b - Previous image", "z - Delete last bounding box",
            "a - Delete ALL bounding boxes", "Enter - Save labels",
            "q - Quit", "? - Show this help",
            "===================================================\n"
        ]
        
        for line in help_text:
            print(line)
    
    def create_data_yaml(self):
        """Membuat file data.yaml untuk training YOLOv5"""
        yaml_content = f"""# SmartCane Dataset YOLOv5
path: {self.dataset_path.absolute()}  # dataset root dir
train: images/train  # train images (relative to path)
val: images/val      # val images (relative to path)
test: images/test    # test images (relative to path)

# Classes
nc: {len(self.classes)}  # number of classes
names: {list(self.classes.keys())}  # class names
"""
        
        yaml_file = self.dataset_path / "data.yaml"
        with open(yaml_file, 'w') as f:
            f.write(yaml_content)
        
        print(f"Created data.yaml at: {yaml_file}")
    
    def run(self):
        if not self.image_files:
            print(f"Tidak ada gambar yang ditemukan di {self.images_dir}")
            print("Pastikan gambar berada di folder 'images' dalam dataset directory")
            print("Format yang didukung: JPG, JPEG, PNG, BMP, TIFF, WEBP")
            return
        
        self.show_help()
        
        cv2.namedWindow('YOLOv5 Labeler - SmartCane')
        cv2.setMouseCallback('YOLOv5 Labeler - SmartCane', self.mouse_callback)
        
        while self.current_image_index < len(self.image_files):
            image_path = self.image_files[self.current_image_index]
            self.current_image = cv2.imread(str(image_path))
            
            if self.current_image is None:
                print(f"Gagal memuat gambar: {image_path}")
                self.current_image_index += 1
                continue
            
            # Resize gambar untuk display
            self.display_image = self.resize_image_for_display(self.current_image)
            
            # Load existing labels untuk gambar ini
            self.load_existing_labels()
            
            print(f"\nGambar {self.current_image_index + 1}/{len(self.image_files)}: {image_path.name}")
            print(f"Current class: {self.current_class}")
            print(f"Number of boxes: {len(self.current_boxes)}")
            
            self.redraw_image()
            
            while True:
                key = cv2.waitKey(1) & 0xFF
                
                if key in self.keyboard_mapping:
                    self.current_class = self.keyboard_mapping[key]
                    print(f"Class changed to: {self.current_class}")
                    self.redraw_image()
                
                elif key == ord('n'):  # Next image
                    self.save_labels()
                    self.current_image_index += 1
                    break
                
                elif key == ord('b'):  # Previous image
                    self.save_labels()
                    self.current_image_index = max(0, self.current_image_index - 1)
                    break
                
                elif key == ord('z'):  # Delete last bounding box
                    if self.current_boxes:
                        removed_box = self.current_boxes.pop()
                        print(f"Deleted box: {removed_box[4]} {removed_box[:4]}")
                        self.redraw_image()
                    else:
                        print("No boxes to delete")
                
                elif key == ord('a'):  # Delete ALL bounding boxes
                    if self.current_boxes:
                        print(f"Deleted ALL {len(self.current_boxes)} boxes")
                        self.current_boxes = []
                        self.redraw_image()
                    else:
                        print("No boxes to delete")
                
                elif key == 13:  # Enter - Save
                    self.save_labels()
                    print("Labels saved!")
                
                elif key == ord('?'):  # Help
                    self.show_help()
                
                elif key == ord('q'):  # Quit
                    self.save_labels()
                    cv2.destroyAllWindows()
                    print("Labeling session ended.")
                    return
            
            if self.current_image_index >= len(self.image_files):
                print("\nSemua gambar telah diproses!")
                break
        
        cv2.destroyAllWindows()
        
        # Buat data.yaml setelah selesai labeling
        self.create_data_yaml()
        print("\nLabeling selesai!")
        print(f"Total gambar yang diproses: {len(self.image_files)}")
        print(f"File data.yaml telah dibuat untuk training YOLOv5")

def main():
    parser = argparse.ArgumentParser(description='YOLOv5 Labeling Tool for SmartCane')
    parser.add_argument('--dataset', type=str, default='dataset', 
                       help='Path to dataset directory (default: dataset)')
    parser.add_argument('--max-width', type=int, default=1280,
                       help='Maximum display width in pixels (default: 1280)')
    parser.add_argument('--max-height', type=int, default=720,
                       help='Maximum display height in pixels (default: 720)')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("YOLOv5 Labeling Tool - SmartCane")
    print("=" * 50)
    
    labeler = YOLOv5Labeler(args.dataset, args.max_width, args.max_height)
    labeler.run()

if __name__ == "__main__":
    main()