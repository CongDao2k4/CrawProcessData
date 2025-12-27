import csv
import datetime
import os
import re
import traceback
import pandas as pd


def get_list_file_by_os(input_dir='data_bonbanh'):
    file_paths = set()
    raw_dir = os.path.join(input_dir, "raw")
    for filename in os.listdir(raw_dir):
        if filename.endswith('.csv'):
            file_path = os.path.join(raw_dir, filename)
            file_paths.add(file_path)
    print(*file_paths, sep='\n')
    return list(file_paths)


def split_name_and_price(s):
    if pd.isna(s):
        return pd.Series([None, None])
    s_str = str(s)
    if '-' in s_str:
        parts = s_str.rsplit('-', 1)
        if len(parts) == 2:
            return pd.Series([parts[0].strip(), parts[1].strip()])
    return pd.Series([s_str.strip(), None])


def normalize_price(price_str):
    """Chuyển đổi giá về đơn vị triệu VNĐ"""
    if pd.isna(price_str):
        return None
    price_str = str(price_str).strip()
    # Tìm tất cả các số trong chuỗi
    numbers = re.findall(r'\d+', price_str)
    if not numbers:
        return None

    # Chuyển đổi dựa trên đơn vị
    if 'Tỷ' in price_str or 'tỷ' in price_str:
        ty = int(numbers[0]) * 1000  # 1 tỷ = 1000 triệu
        trieu = int(numbers[1]) if len(numbers) > 1 else 0
        return ty + trieu
    elif 'Triệu' in price_str or 'triệu' in price_str:
        return int(numbers[0])
    else:
        return int(numbers[0])


def extract_daytime(s):
    if pd.isna(s):
        return None
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if match:
        day, month, year = map(int, match.groups())
        date_obj = datetime.datetime(year, month, day)
        return str(date_obj.strftime(f"%d/%m/%Y"))
    return None


def parse_km(s):
    if pd.isna(s):
        return 0
    if not isinstance(s, str):
        return 0
    # Xóa mọi ký tự không phải số
    digits = re.sub(r'[^\d]', '', s)
    return int(digits) if digits else 0

def preprocess(csv_file_name, output_dir='data_bonbanh'):
    try:
        os.makedirs(os.path.join(output_dir, "processed"), exist_ok=True)
        file_csv_path = os.path.join(output_dir, "raw", csv_file_name)
        processed_file_path = os.path.join(output_dir, "processed", "processed_" + csv_file_name)

        if not os.path.exists(file_csv_path):
            print(f"    Không tìm thấy file tên {os.path.basename(file_csv_path)}")
            return

        dataframe = pd.read_csv(file_csv_path, encoding='utf-8',usecols=list(range(9))+[18])

        # Áp dụng hàm lên CỘT ĐẦU TIÊN (index 0)
        dataframe[['name', 'price']] = dataframe.iloc[:, 0].apply(split_name_and_price)
        # Áp dụng cho cột price
        dataframe['price'] = dataframe['price'].apply(normalize_price)
        # Lấy ngày ra khỏi cột sell_time
        dataframe['sell_time'] = dataframe['sell_time'].apply(extract_daytime)
        # Áp dụng lấy số km đã đi
        dataframe['traveled_kilometer'] = dataframe['traveled_kilometer'].apply(parse_km)
        # Điền vào các ô trống trong cột địa chỉ
        dataframe.fillna({'owner_address': 'Không có'}, inplace=True)
        # print(dataframe[['name','sell_time','price','traveled_kilometer']].head(50))

        if os.path.exists(processed_file_path):
            dataframe.to_csv(processed_file_path, mode='a', index=False, encoding='utf-8', header=False)
        else:
            dataframe.to_csv(processed_file_path, mode='w', index=False, encoding='utf-8', header=True)

        print(f"✓ Đã xử lý {len(dataframe)} dòng từ {os.path.basename(csv_file_name)}")

    except Exception as e:
        print(f"Lỗi lúc xử lý dữ liệu thô: {str(e)}")
        print(traceback.format_exc())  # In chi tiết stack trace

if __name__ == '__main__':
    # preprocess('info_cars 1520_1999.csv')
    preprocess('raw_cars.csv')
