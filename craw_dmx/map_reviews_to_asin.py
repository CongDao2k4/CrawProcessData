import os
import glob
import json
import logging
import sys
import pandas as pd

# ==========================================
# CẤU HÌNH THƯ MỤC
# ==========================================
CSV_MAPPING_FILE = os.path.join('dmx_links_mapped_asin', 'product_asin_mapping_ai.csv')
INPUT_JSONL_DIR = 'dmx_reviews'
OUTPUT_JSONL_DIR = 'mapped_dmx_reviews_output'  # Thư mục mới chứa kết quả


def init_logging():
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler("map_reviews_asin.log", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )


def load_mapping_dict(csv_file):
    """Đọc file CSV và tạo dictionary {product_id: asin} siêu tốc"""
    if not os.path.exists(csv_file):
        logging.error(f"❌ Không tìm thấy file mapping: {csv_file}")
        return {}

    try:
        df = pd.read_csv(csv_file)

        # Chỉ lấy các dòng đã được Map thành công
        if 'match_status' in df.columns:
            df = df[df['match_status'] == 'Matched']

        # Xóa các dòng bị null/trống ở cột matched_asin
        df = df.dropna(subset=['matched_asin'])

        # Tạo dictionary { "335362": "B0Cxyz...", ... }
        mapping_dict = dict(zip(df['product_id'].astype(str), df['matched_asin'].astype(str)))

        logging.info(f"✅ Đã nạp {len(mapping_dict)} cặp (Product ID -> ASIN) từ file mapping.")
        return mapping_dict
    except Exception as e:
        logging.error(f"❌ Lỗi đọc file mapping: {e}")
        return {}


def process_reviews(input_dir, output_dir, mapping_dict):
    """Quét các file JSONL, cấy thêm ASIN và xuất ra thư mục mới"""
    os.makedirs(output_dir, exist_ok=True)
    jsonl_files = glob.glob(os.path.join(input_dir, '*.jsonl'))

    if not jsonl_files:
        logging.warning(f"⚠️ Không tìm thấy file .jsonl nào trong '{input_dir}'.")
        return

    logging.info(f"🚀 Bắt đầu thêm ASIN cho {len(jsonl_files)} file JSONL...")

    total_reviews = 0
    total_mapped = 0

    for filepath in jsonl_files:
        filename = os.path.basename(filepath)
        output_filepath = os.path.join(output_dir, filename)

        mapped_in_file = 0
        total_in_file = 0

        try:
            # Vừa đọc file cũ, vừa ghi thẳng ra file mới từng dòng để tiết kiệm RAM
            with open(filepath, 'r', encoding='utf-8') as infile, \
                    open(output_filepath, 'w', encoding='utf-8') as outfile:

                for line in infile:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        total_in_file += 1
                        total_reviews += 1

                        # Lấy product_id ép kiểu string để tra dictionary
                        prod_id = str(data.get('productId', ''))

                        # Tra cứu ASIN
                        if prod_id in mapping_dict:
                            data['asin'] = mapping_dict[prod_id]  # Cấy thêm thuộc tính asin
                            mapped_in_file += 1
                            total_mapped += 1
                        else:
                            # Nếu sản phẩm này không map được bên AI, gắn null
                            data['asin'] = None

                        # Dump lại thành JSON và ghi vào file mới (đảm bảo không bị lỗi font tiếng Việt)
                        outfile.write(json.dumps(data, ensure_ascii=False) + '\n')

                    except json.JSONDecodeError:
                        logging.error(f"    ❌ Lỗi parse JSON ở file {filename}: {line[:50]}...")

            logging.info(f"    - {filename}: {mapped_in_file}/{total_in_file} reviews được gắn ASIN.")

        except Exception as e:
            logging.error(f"    ❌ Lỗi xử lý file {filename}: {e}")

    logging.info("\n=======================================")
    logging.info(f"🏁 BÁO CÁO KẾT QUẢ GẮN ASIN VÀO REVIEWS:")
    logging.info(f"   - Tổng số Review đã quét: {total_reviews}")
    # Tránh chia cho 0 nếu file trống
    percent_mapped = round((total_mapped / total_reviews) * 100, 2) if total_reviews > 0 else 0
    logging.info(f"   - Tổng số Review được gắn ASIN: {total_mapped} ({percent_mapped}%)")
    logging.info(f"   - Thư mục đầu ra lưu tại: {output_dir}")
    logging.info("=======================================\n")


if __name__ == "__main__":
    init_logging()

    # 1. Khởi tạo kho dữ liệu tra cứu
    mapping_dict = load_mapping_dict(CSV_MAPPING_FILE)

    # 2. Thực hiện cấy ghép
    if mapping_dict:
        process_reviews(INPUT_JSONL_DIR, OUTPUT_JSONL_DIR, mapping_dict)
    else:
        logging.error("❌ Dừng chương trình vì không có dữ liệu mapping hợp lệ.")