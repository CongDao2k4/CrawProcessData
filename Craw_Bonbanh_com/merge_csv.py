import tkinter as tk
from tkinter import filedialog
import os
import csv


def select_files():
    '''Lấy theo cách mở cửa sổ và chọn từng file vào => có cách thay bằng filedialog.askopenfilenames() để 1 lần chọn được nhiều file '''
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính
    root.attributes('-topmost', True)  # Đưa dialog lên trên cùng

    list_file_path = []
    while input("Muốn thêm file csv (y= yes, n = no) :") == 'y':
        file_path = filedialog.askopenfilename(
            parent=root,
            title='Chọn file CSV',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')]
        )
        if file_path:  # Kiểm tra nếu user có chọn file
            list_file_path.append(file_path)
            print(f"Đã chọn: {file_path}")
        else:
            print("Không chọn file nào")

    root.destroy()  # Đóng cửa sổ Tkinter
    return list(set(list_file_path))


def get_file_paths():
    """Lấy danh sách đường dẫn file từ hàm select_files"""
    csv_file_child_paths = select_files()
    return csv_file_child_paths

def get_list_file_by_os(input_dir = 'data_bonbanh'):
    file_paths = set()
    raw_dir = os.path.join(input_dir, "raw")
    for filename in os.listdir(raw_dir):
        if filename.endswith('.csv'):
            file_path = os.path.join(raw_dir, filename)
            file_paths.add(file_path)
    print(*file_paths,sep='\n')
    return list(file_paths)

def append_to_csv(csv_file_child_path, csv_file_parent='raw_cars.csv', output_dir='data_bonbanh'):
    """Gộp một file CSV con vào file CSV cha"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, csv_file_parent)
        file_exists = os.path.exists(file_path)

        # Đọc file con để lấy fieldnames thực tế
        with open(csv_file_child_path, 'r', encoding='utf-8') as child_file:
            reader = csv.DictReader(child_file)
            fieldnames = reader.fieldnames  # Lấy tên cột từ file gốc
            rows = list(reader)  # Đọc tất cả dữ liệu

        # Ghi vào file cha
        with open(file_path, 'a+', newline='', encoding='utf-8') as csvFile:
            writer = csv.DictWriter(csvFile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()  # Ghi header nếu file chưa tồn tại

            # Ghi tất cả các dòng
            for row in rows:
                writer.writerow(row)

            print(f"✓ Đã gộp {len(rows)} dòng từ {os.path.basename(csv_file_child_path)}")

    except Exception as e:
        print(f"✗ Lỗi khi xử lý {os.path.basename(csv_file_child_path)}: {str(e)}")


def merge_all_csv_files():
    """Hàm chính để gộp tất cả file CSV được chọn"""
    print("=== BẮT ĐẦU CHỌN FILE CSV ===")
    csv_file_child_paths = get_file_paths()
    # csv_file_child_paths = get_list_file_by_os()

    if not csv_file_child_paths:
        print("Không có file nào được chọn!")
        return

    print(f"\n=== ĐÃ CHỌN {len(csv_file_child_paths)} FILE ===")
    for path in csv_file_child_paths:
        print(f"  - {path}")

    print("\n=== BẮT ĐẦU GỘP FILE ===")
    for csv_path in csv_file_child_paths:
        append_to_csv(csv_path)

    print("\n=== HOÀN THÀNH ===")
    print(f"Đã gộp {len(csv_file_child_paths)} file vào raw_cars.csv")

# Chạy chương trình
if __name__ == "__main__":
    # get_list_file_by_os()
    merge_all_csv_files()