import json
import random
import time
import os
import logging
import sys
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc


def init(output_dir='dmx_metadata_output'):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    file_handler = logging.FileHandler("dmx_metadata_scraper.log", encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(stream_handler)

    abs_path = os.path.abspath(output_dir)
    os.makedirs(abs_path, exist_ok=True)
    logging.info(f"🚀 Hệ thống khởi tạo thành công. Thư mục lưu kết quả: {abs_path}")
    return abs_path

def get_chrome_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

    try:
        driver = uc.Chrome(options=options, version_main=146)
        driver.set_page_load_timeout(45)
        return driver
    except Exception as e:
        logging.error(f"❌ Lỗi khởi tạo driver: {e}")
        time.sleep(5)
        return get_chrome_driver()

def safe_get_html(driver, css_selector):
    """Hàm an toàn lấy innerHTML để giữ nguyên định dạng bảng thông số và ảnh mô tả"""
    try:
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        # Sử dụng innerHTML để bảo toàn cấu trúc <table> hoặc <p> của DMX
        return element.get_attribute("innerHTML").strip()
    except:
        return None

def extract_dmx_metadata(driver, url, p_id, p_name):
    try:
        driver.get(url)
        time.sleep(random.uniform(2.5, 4.0))  # Đợi JS render
        wait = WebDriverWait(driver, 10)

        if "captcha" in driver.current_url.lower() or "404" in driver.title:
            return "RESTART" if "captcha" in driver.current_url.lower() else None

        # Đợi cho phần tử chính box_main xuất hiện
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.box_main")))
        except TimeoutException:
            pass  # Vẫn cố lấy nếu load chậm
        # -- Cố gắng bấm các nút "Xem thêm cấu hình / Xem thêm nội dung" --
        try:
            # Các class phổ biến của nút Xem thêm trên DMX
            view_more_btns = driver.find_elements(By.CSS_SELECTOR, ".btn-detail, .btn-show-more, .read-more")
            for btn in view_more_btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
            time.sleep(1.5)  # Đợi bung HTML sau khi click
        except:
            pass

        spec_list = []
        try:
            # Tìm tất cả các thẻ <li> nằm trong div specifications (tab-1)
            # Nếu web dùng Table, bạn có thể đổi thành "#tab-1 tr"
            li_elements = driver.find_elements(By.CSS_SELECTOR, "#tab-1 li")

            for li in li_elements:
                text = li.text.strip()
                if text:  # Chỉ thêm nếu có nội dung
                    # Thay thế dấu xuống dòng bằng dấu cách để dữ liệu phẳng
                    spec_list.append(text.replace('\n', ': '))
            logging.info(f"    Đã lấy được {len(spec_list)} thuộc tính")
        except Exception as e:
            logging.warning(f"    Không lấy được danh sách <li> tại {url}: {e}")

        # Giữ nguyên lấy HTML cho bài viết để bảo toàn định dạng bài blog/ảnh
        # description = ""
        # try:
        #     desc_el = driver.find_element(By.CSS_SELECTOR, "#tab-2")
        #     description = desc_el.get_attribute("innerHTML").strip()
        #     logging.info("    Đã lấy được Thông tin mô tả sản phẩm")
        # except Exception as e:
        #     logging.warning(f"    Không lấy được Thông tin mô tả sản phẩm , lỗi: {e}")
        #     pass
        #

        # --- XỬ LÝ LẤY MÔ TẢ (DESCRIPTION) ---
        description = ""
        # Danh sách các selector dự phòng thường được DMX/TGDD sử dụng
        desc_selectors = [ "div#tab-2.description", "#tab-2", ".article.content-t-wrap", ".area_article", ".content-article" ]

        for sel in desc_selectors:
            try:
                desc_el = driver.find_element(By.CSS_SELECTOR, sel)
                description = desc_el.get_attribute("innerHTML").strip()
                if description:
                    break  # Nếu lấy được nội dung thì thoát vòng lặp tìm kiếm
            except:
                continue  # Nếu không tìm thấy selector này thì thử selector tiếp theo
        if description:
            logging.info("      Đã lấy được Thông tin mô tả sản phẩm")
        else:
            # Chỉ in ra cảnh báo ngắn gọn thay vì in toàn bộ Stacktrace dài dòng
            logging.warning("      [!] Sản phẩm này không có bài viết mô tả.")

        return {
            "product_id": p_id,
            "product_name": p_name,
            "product_url": url,
            "specifications": spec_list,  # Bây giờ là một List [ "RAM: 8GB", "SSD: 512GB", ... ]
            "description": description
        }
    except TimeoutException:
        logging.warning(f"⏳ Timeout khi tải trang: {url}")
        return None
    except Exception as e:
        logging.error(f"❌ Lỗi extract tại {url}: {str(e)}")
        return "RESTART"

def process_dmx_metadata(source_dir, output_dir):
    init(output_dir)
    if not os.path.exists(source_dir):
        logging.error(f"⚠️ Thư mục nguồn '{source_dir}' không tồn tại. Vui lòng tạo và thêm file CSV vào.")
        return
    driver = get_chrome_driver()
    try:
        for file_name in os.listdir(source_dir):
            if not file_name.endswith('.csv'):
                continue
            full_csv_path = os.path.join(source_dir, file_name)
            save_name = file_name.replace('.csv', '_metadata.jsonl')
            full_json_path = os.path.join(output_dir, save_name)
            logging.info(f"📂 ĐANG XỬ LÝ: File {file_name}")
            # Đọc CSV
            df = pd.read_csv(full_csv_path, low_memory=False)
            # Check cột bắt buộc
            required_cols = ['product_id', 'product_url', 'product_name']
            if not all(col in df.columns for col in required_cols):
                logging.warning(f"⚠️ File {file_name} thiếu cột bắt buộc {required_cols}. Bỏ qua.")
                continue
            batch_results = []
            processed_count = 0
            for idx, row in df.iterrows():
                processed_count += 1
                # Refresh session định kỳ mỗi 15 sản phẩm
                if processed_count % 15 == 0:
                    logging.info("♻️ Làm mới Driver để ổn định session...")
                    driver.quit()
                    driver = get_chrome_driver()
                p_url = str(row['product_url'])
                p_id = str(row['product_id'])
                p_name = str(row['product_name'])
                if pd.isna(p_url) or not p_url.startswith("http"):
                    continue
                retry_count = 0
                metadata = None
                while retry_count < 3:
                    logging.info(f"   🔹 [{idx + 1}/{len(df)}] Lấy Metadata: {p_url}")
                    result = extract_dmx_metadata(driver, p_url, p_id, p_name)
                    if result == "RESTART":
                        logging.warning("🛑 Dính lỗi nặng/session. Đang khởi động lại trình duyệt...")
                        driver.quit()
                        time.sleep(random.uniform(3, 5))
                        driver = get_chrome_driver()
                        retry_count += 1
                    elif result:
                        metadata = result
                        break
                    else:
                        retry_count += 1
                if metadata:
                    batch_results.append(metadata)
                # Lưu theo batch 20 cái
                if len(batch_results) >= 10:
                    with open(full_json_path, 'a', encoding='utf-8') as f:
                        for item in batch_results:
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    logging.info(f"      💾 Đã ghi batch {len(batch_results)} items vào {save_name}")
                    batch_results = []
                time.sleep(random.uniform(1.0, 2.5))
            # Lưu tệp cuối cùng còn thừa
            if batch_results:
                with open(full_json_path, 'a', encoding='utf-8') as f:
                    for item in batch_results:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                logging.info(f"      💾 Đã ghi {len(batch_results)} items cuối vào {save_name}")
            logging.info(f"✅ Hoàn tất file: {file_name}")
    finally:
        if driver:
            driver.quit()
        logging.info("🏁 TOÀN BỘ QUY TRÌNH HOÀN TẤT.")

if __name__ == "__main__":
    # Tham số: (Thư mục chứa file CSV links, Thư mục lưu file JSONL output)
    process_dmx_metadata('dmx_links', 'dmx_metadata_output')