import os
import glob
import json
import logging
import sys
import pandas as pd
from bs4 import BeautifulSoup

# ==========================================
# CẤU HÌNH THƯ MỤC
# ==========================================
CSV_MAPPING_FILE = os.path.join('dmx_links_mapped_asin', 'product_asin_mapping_ai.csv')
INPUT_JSONL_DIR = 'dmx_metadata_output'
OUTPUT_JSONL_DIR = 'cleaned_mapped_metadata'  # Thư mục xuất file sạch


def init_logging():
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler("metadata_cleaning.log", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )


def load_mapping_dict(csv_file):
    """Đọc file CSV và tạo dictionary {product_id: asin}"""
    if not os.path.exists(csv_file):
        logging.error(f"❌ Không tìm thấy file mapping: {csv_file}")
        return {}

    try:
        df = pd.read_csv(csv_file)
        # Chỉ lấy các dòng Matched có ASIN hợp lệ
        if 'match_status' in df.columns:
            df = df[df['match_status'] == 'Matched']
        df = df.dropna(subset=['matched_asin'])

        mapping_dict = dict(zip(df['product_id'].astype(str), df['matched_asin'].astype(str)))
        logging.info(f"✅ Đã nạp {len(mapping_dict)} cặp (Product ID -> ASIN).")
        return mapping_dict
    except Exception as e:
        logging.error(f"❌ Lỗi đọc file mapping: {e}")
        return {}


def clean_html_content(raw_html):
    """Dùng BeautifulSoup để lột bỏ toàn bộ thẻ HTML, chỉ giữ lại văn bản thuần"""
    if not raw_html or not isinstance(raw_html, str):
        return ""
    try:
        # Lột bỏ thẻ HTML, thay thế các tag bằng 1 dấu cách để chữ không bị dính vào nhau
        soup = BeautifulSoup(raw_html, "html.parser")
        clean_text = soup.get_text(separator=' ', strip=True)
        return clean_text
    except Exception:
        return raw_html  # Fallback nếu có lỗi lạ


def process_metadata(input_dir, output_dir, mapping_dict):
    """Quét các file JSONL, làm sạch mô tả và cấy thêm ASIN"""
    os.makedirs(output_dir, exist_ok=True)
    jsonl_files = glob.glob(os.path.join(input_dir, '*.jsonl'))

    if not jsonl_files:
        logging.warning(f"⚠️ Không tìm thấy file .jsonl nào trong '{input_dir}'.")
        return

    logging.info(f"🚀 Bắt đầu lột HTML và cấy ASIN cho {len(jsonl_files)} file...")

    total_processed = 0
    total_mapped = 0

    for filepath in jsonl_files:
        filename = os.path.basename(filepath)
        output_filepath = os.path.join(output_dir, filename)

        file_processed = 0
        file_mapped = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as infile, \
                    open(output_filepath, 'w', encoding='utf-8') as outfile:

                for line in infile:
                    line = line.strip()
                    if not line: continue

                    try:
                        data = json.loads(line)
                        total_processed += 1
                        file_processed += 1

                        # 1. LỘT BỎ HTML RÁC TRONG DESCRIPTION
                        raw_desc = data.get('description', '')
                        data['description'] = clean_html_content(raw_desc)

                        # 2. GHÉP NỐI ASIN
                        prod_id = str(data.get('product_id', ''))
                        if prod_id in mapping_dict:
                            data['asin'] = mapping_dict[prod_id]
                            file_mapped += 1
                            total_mapped += 1
                        else:
                            data['asin'] = None

                        # Ghi dòng JSON mới ra file
                        outfile.write(json.dumps(data, ensure_ascii=False) + '\n')

                    except json.JSONDecodeError:
                        logging.error(f"    ❌ Lỗi parse JSON ở file {filename}: {line[:50]}...")

            logging.info(f"    - {filename}: Đã làm sạch & gắn ASIN thành công ({file_mapped}/{file_processed}).")

        except Exception as e:
            logging.error(f"    ❌ Lỗi xử lý file {filename}: {e}")

    logging.info("\n=======================================")
    logging.info(f"🏁 BÁO CÁO KẾT QUẢ XỬ LÝ METADATA:")
    logging.info(f"   - Tổng số Metadata JSON đã quét: {total_processed}")
    percent_mapped = round((total_mapped / total_processed) * 100, 2) if total_processed > 0 else 0
    logging.info(f"   - Số lượng cấy ASIN thành công: {total_mapped} ({percent_mapped}%)")
    logging.info(f"   - Thư mục đầu ra sạch sẽ: {output_dir}")
    logging.info("=======================================\n")


if __name__ == "__main__":
    init_logging()

    # Khởi tạo từ điển ánh xạ
    mapping_dict = load_mapping_dict(CSV_MAPPING_FILE)

    # Xử lý dữ liệu
    process_metadata(INPUT_JSONL_DIR, OUTPUT_JSONL_DIR, mapping_dict)