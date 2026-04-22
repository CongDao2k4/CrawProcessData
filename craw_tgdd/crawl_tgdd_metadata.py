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


# --- Cấu hình Logging ---
def init(output_dir='tgdd_metadata_output'):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    file_handler = logging.FileHandler("tgdd_metadata_scraper.log", encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(stream_handler)

    abs_path = os.path.abspath(output_dir)
    os.makedirs(abs_path, exist_ok=True)
    logging.info(f"🚀 Hệ thống khởi tạo thành công. Lưu kết quả tại: {abs_path}")
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
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(100)
        return driver
    except Exception as e:
        logging.error(f"❌ Lỗi khởi tạo driver: {e}")
        time.sleep(5)
        return get_chrome_driver()


# --- Logic trích xuất TGDD ---
def extract_tgdd_metadata(driver, url, p_id, p_name):
    try:
        driver.get(url)
        time.sleep(random.uniform(3.0, 4.5))
        wait = WebDriverWait(driver, 100)

        if "captcha" in driver.current_url.lower() or "404" in driver.title:
            return "RESTART" if "captcha" in driver.current_url.lower() else None

        # Đợi box chính xuất hiện
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".box_main")))
        except:
            pass

        # Bấm nút mở rộng (Xem thêm cấu hình / Xem bài viết)
        try:
            # TGDD thường dùng các class này cho nút mở rộng
            expand_btns = driver.find_elements(By.CSS_SELECTOR, ".btn-detail, .btn-show-more, .read-more, .btn-re-more")
            for btn in expand_btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
        except:
            pass

        # 1. Trích xuất Thông số kỹ thuật (dạng List các li)
        spec_list = []
        try:
            # Theo yêu cầu: class specifications tab-content current, id = tab-1
            # Lấy tất cả li bên trong
            spec_elements = driver.find_elements(By.CSS_SELECTOR, "#tab-1.specifications li")
            for li in spec_elements:
                txt = li.text.strip()
                if txt:
                    spec_list.append(txt.replace('\n', ': '))
            logging.info(f"    Đã lấy được {len(spec_list)} thuộc tính")
        except:
            logging.warning(f"    Không lấy được danh sách <li> tại {url}")

        # 2. Trích xuất Thông tin sản phẩm (dạng HTML)
        description_html = ""
        try:
            # Theo yêu cầu: class description tab-content short, id = tab-2 (hoặc tab2)
            desc_selectors = ["#tab-2", "#tab2", ".description.tab-content", ".content-article"]
            for sel in desc_selectors:
                try:
                    desc_el = driver.find_element(By.CSS_SELECTOR, sel)
                    description_html = desc_el.get_attribute("innerHTML").strip()
                    if description_html:
                        logging.info("      Đã lấy được Thông tin mô tả sản phẩm")
                        break
                except:
                    continue
        except:
            logging.warning("      [!] Sản phẩm này không có bài viết mô tả.")

        return {
            "product_id": p_id,
            "product_name": p_name,
            "product_url": url,
            "specifications": spec_list,
            "description": description_html
        }
    except TimeoutException:
        logging.warning(f"⏳ Timeout khi tải trang: {url}")
        return None
    except Exception as e:
        logging.error(f"❌ Lỗi xử lý tại {url}: {str(e)}")
        return "RESTART"


def process_tgdd_metadata(source_dir, output_dir):
    init(output_dir)

    if not os.path.exists(source_dir):
        logging.error(f"⚠️ Thư mục nguồn '{source_dir}' không tồn tại.")
        return

    driver = get_chrome_driver()
    processed_count = 0

    try:
        for file_name in os.listdir(source_dir):
            if not file_name.endswith('.csv'): continue

            full_csv_path = os.path.join(source_dir, file_name)
            save_name = file_name.replace('.csv', '_metadata.jsonl')
            full_json_path = os.path.join(output_dir, save_name)

            logging.info(f"📂 ĐANG XỬ LÝ FILE: {file_name}")
            df = pd.read_csv(full_csv_path, low_memory=False)

            batch_results = []

            for idx, row in df.iterrows():
                processed_count += 1
                # Refresh session định kỳ 15 sản phẩm để tránh treo Chrome
                if processed_count % 15 == 0:
                    logging.info("♻️ Đang làm mới trình duyệt...")
                    driver.quit()
                    driver = get_chrome_driver()

                p_url = str(row['product_url'])
                p_id = str(row['product_id'])
                p_name = str(row['product_name'])

                if pd.isna(p_url) or not p_url.startswith("http"): continue

                retry = 0
                metadata = None
                while retry < 3:
                    logging.info(f"   🔹 [{idx + 1}/{len(df)}] Thu thập: {p_url}")
                    result = extract_tgdd_metadata(driver, p_url, p_id, p_name)

                    if result == "RESTART":
                        driver.quit()
                        time.sleep(5)
                        driver = get_chrome_driver()
                        retry += 1
                    elif result:
                        metadata = result
                        break
                    else:
                        retry += 1

                if metadata:
                    batch_results.append(metadata)

                # Lưu batch 10-20 items
                if len(batch_results) >= 10:
                    with open(full_json_path, 'a', encoding='utf-8') as f:
                        for item in batch_results:
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    logging.info(f"      💾 Đã lưu batch {len(batch_results)} items.")
                    batch_results = []

                time.sleep(random.uniform(1.0, 2.0))

            # Lưu phần dư cuối cùng
            if batch_results:
                with open(full_json_path, 'a', encoding='utf-8') as f:
                    for item in batch_results:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")

            logging.info(f"✅ Hoàn tất file: {file_name}")

    finally:
        if driver: driver.quit()
        logging.info("🏁 TOÀN BỘ QUY TRÌNH HOÀN TẤT.")


if __name__ == "__main__":
    # Đọc từ tgdd_links và xuất ra tgdd_metadata_output
    process_tgdd_metadata('tgdd_links', 'tgdd_metadata_output')