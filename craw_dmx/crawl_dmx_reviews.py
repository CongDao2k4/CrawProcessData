import os
import time
import json
import re
import logging
import random
import pandas as pd
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


# --- Cấu hình hệ thống ---
def init_logging():
    # Xóa các handler cũ để không bị in trùng dòng (tránh log lặp)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("dmx_review_crawl_v2.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("🚀 Hệ thống cào Điện Máy Xanh (Trang gốc + Pages) đã sẵn sàng.")


def get_driver():
    options = uc.ChromeOptions()  # Đổi từ Options() sang uc.ChromeOptions() để tương thích tốt nhất
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--incognito")  # Dùng ẩn danh để tránh lưu session lỗi
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = uc.Chrome(options=options, version_main=146)
    driver.set_page_load_timeout(35)  # Tăng thêm timeout cho an toàn

    return driver


# --- Tiện ích xử lý dữ liệu ---
def parse_relative_time(time_str):
    """Tính toán thời gian ngẫu nhiên linh động dựa trên chuỗi tương đối"""
    now = datetime.now()
    match = re.search(r'(\d+)', time_str)
    n = int(match.group(1)) if match else 1

    # Xác định biên độ ngẫu nhiên
    if "giây" in time_str or "phút" in time_str:
        min_diff, max_diff = timedelta(minutes=1), timedelta(minutes=n if "phút" in time_str else 2)
    elif "giờ" in time_str:
        min_diff, max_diff = timedelta(hours=n), timedelta(hours=n + 1)
    elif "ngày" in time_str:
        min_diff, max_diff = timedelta(days=n), timedelta(days=n + 1)
    elif "tuần" in time_str:
        min_diff, max_diff = timedelta(days=n * 7), timedelta(days=(n + 1) * 7)
    elif "tháng" in time_str:
        min_diff, max_diff = timedelta(days=n * 30), timedelta(days=(n + 1) * 30)
    elif "năm" in time_str:
        min_diff, max_diff = timedelta(days=n * 365), timedelta(days=(n + 1) * 365)
    else:
        min_diff, max_diff = timedelta(days=1), timedelta(days=2)

    random_sec = random.randint(int(min_diff.total_seconds()), int(max_diff.total_seconds()))
    target_date = now - timedelta(seconds=random_sec)

    return target_date.replace(
        hour=random.randint(0, 23),
        minute=random.randint(0, 59),
        second=random.randint(0, 59)
    ).strftime("%Y-%m-%d %H:%M:%S")


# --- Logic cào chi tiết ---
def get_breadcrumb_dmx(driver, product_url):
    """Vào trang gốc sản phẩm 1 lần duy nhất để lấy Breadcrumb"""
    try:
        driver.get(product_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.breadcrumb")))
        nodes = driver.find_elements(By.CSS_SELECTOR, "ul.breadcrumb li a")
        return " > ".join([n.text.strip() for n in nodes if n.text.strip()])
    except:
        return ""


def extract_reviews_from_main_page_dmx(driver, product_id, breadcrumb_str):
    """HÀM MỚI: Trích xuất review ngay tại trang gốc đang mở"""
    reviews = []
    try:
        # Cuộn xuống khu vực comment để kích hoạt lazy-load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(2)

        items = driver.find_elements(By.CSS_SELECTOR, "ul.comment-list li.par")
        for it in items:
            try:
                name = it.find_element(By.CSS_SELECTOR, ".cmt-top-name").text.strip()
                stars = len(it.find_elements(By.CSS_SELECTOR, ".cmt-top-star i.iconcmt-starbuy"))
                content = it.find_element(By.CSS_SELECTOR, ".cmt-txt").text.strip()

                time_el = it.find_element(By.CSS_SELECTOR, ".cmtd")
                time_raw = time_el.text.strip().replace("Đã dùng khoảng ", "")

                reviews.append({
                    "productId": product_id,
                    "fullName": name,
                    "rating": stars,
                    "content": content,
                    "creationTime": parse_relative_time(time_raw),
                    "breadcrumb": breadcrumb_str
                })
            except Exception:
                continue
    except Exception as e:
        logging.error(f"      [!] Lỗi quét review trang gốc: {e}")
    return reviews


def extract_reviews_dmx(driver, url, product_id, breadcrumb_str):
    """Trích xuất review từ 1 trang /danh-gia?page=x"""
    try:
        driver.get(url)
        time.sleep(3)  # Chờ load AJAX

        # Đợi danh sách comment xuất hiện
        WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.comment-list")))

        if "404" in driver.title or "notfound" in driver.current_url.lower():
            return None
    except:
        return None

    reviews = []
    # Selector dựa trên cấu trúc li.par trong dmx.html
    items = driver.find_elements(By.CSS_SELECTOR, "ul.comment-list li.par")

    if not items:
        return None

    for it in items:
        try:
            name = it.find_element(By.CSS_SELECTOR, ".cmt-top-name").text.strip()
            # Đếm icon sao vàng
            stars = len(it.find_elements(By.CSS_SELECTOR, ".cmt-top-star i.iconcmt-starbuy"))
            content = it.find_element(By.CSS_SELECTOR, ".cmt-txt").text.strip()

            # Xử lý thời gian từ class .cmtd
            time_el = it.find_element(By.CSS_SELECTOR, ".cmtd")
            time_raw = time_el.text.strip().replace("Đã dùng khoảng ", "")

            reviews.append({
                "productId": product_id,
                "fullName": name,
                "rating": stars,
                "content": content,
                "creationTime": parse_relative_time(time_raw),
                "breadcrumb": breadcrumb_str
            })
        except:
            continue
    return reviews


def main():
    init_logging()
    input_dir = 'dmx_links'
    output_dir = 'dmx_reviews_output_v2'
    os.makedirs(output_dir, exist_ok=True)

    driver = get_driver()
    processed_count = 0

    try:
        for file in os.listdir(input_dir):
            if not file.endswith('.csv'): continue

            logging.info(f"===> ĐANG XỬ LÝ FILE: {file}")
            df = pd.read_csv(os.path.join(input_dir, file))
            output_jsonl = os.path.join(output_dir, file.replace('.csv', '.jsonl'))

            for idx, row in df.iterrows():
                # Refresh session định kỳ 10 sản phẩm 1 lần chống treo
                processed_count += 1
                if processed_count % 10 == 0:
                    logging.info("♻️ Làm mới Session trình duyệt...")
                    driver.quit()
                    driver = get_driver()

                base_url = row.get('product_url')
                p_id = str(row.get('product_id'))
                if not base_url or pd.isna(base_url): continue

                # 1. Lấy Breadcrumb từ trang gốc (Hàm cũ)
                logging.info(f" -> [{idx + 1}/{len(df)}] Lấy Breadcrumb & Review trang gốc: {base_url}")
                breadcrumb_str = get_breadcrumb_dmx(driver, base_url)

                seen_reviews = set()
                all_product_reviews = []

                # --- BỔ SUNG: CÀO REVIEW NGAY TẠI TRANG GỐC ---
                main_page_reviews = extract_reviews_from_main_page_dmx(driver, p_id, breadcrumb_str)
                if main_page_reviews:
                    for r in main_page_reviews:
                        # Ký hiệu chống trùng bằng Tên + Nội dung
                        sig = f"{r['fullName']}_{r['content'][:50]}"
                        if sig not in seen_reviews:
                            seen_reviews.add(sig)
                            all_product_reviews.append(r)
                    logging.info(f"      ✅ Thu được {len(main_page_reviews)} reviews từ trang gốc.")

                # 2. Chuẩn bị link đánh giá phân trang
                clean_url = base_url.split('?')[0].rstrip('/')
                review_base_url = f"{clean_url}/danh-gia"

                page = 1
                not_found_count = 0

                # 3. Cào từng trang review
                while not_found_count < 2:  # Để lên 5 cho an toàn hết page
                    target_url = f"{review_base_url}?page={page}"
                    logging.info(f"      - Đang quét Page {page}: {target_url}")

                    try:
                        page_reviews = extract_reviews_dmx(driver, target_url, p_id, breadcrumb_str)

                        if page_reviews:
                            not_found_count = 0  # Có dữ liệu thì reset count lỗi

                            added_in_page = 0
                            for r in page_reviews:
                                sig = f"{r['fullName']}_{r['content'][:50]}"
                                if sig not in seen_reviews:
                                    seen_reviews.add(sig)
                                    all_product_reviews.append(r)
                                    added_in_page += 1

                            logging.info(f"        ✅ Thêm {added_in_page} reviews mới từ Page {page}.")

                            # Lưu batch 20 cái
                            if len(all_product_reviews) >= 20:
                                with open(output_jsonl, 'a', encoding='utf-8') as f:
                                    for r in all_product_reviews:
                                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                                logging.info(f"        💾 Đã lưu {len(all_product_reviews)} reviews.")
                                all_product_reviews = []
                        else:
                            not_found_count += 1
                            logging.warning(f"        [!] Không thấy dữ liệu hoặc Trống (Lần lỗi {not_found_count}/5)")

                    except (WebDriverException, TimeoutException):
                        logging.warning("        [!] Driver treo, đang khởi động lại...")
                        driver.quit()
                        driver = get_driver()
                        not_found_count += 1

                    page += 1
                    time.sleep(random.uniform(1.5, 3))

                # Lưu nốt số còn lại của sản phẩm này
                if all_product_reviews:
                    with open(output_jsonl, 'a', encoding='utf-8') as f:
                        for r in all_product_reviews:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    logging.info(f"        💾 Đã lưu {len(all_product_reviews)} reviews cuối.")

                logging.info(f" ✅ Hoàn tất cào sản phẩm: {p_id}")

    finally:
        if driver:
            driver.quit()
        logging.info("🏁 TOÀN BỘ QUY TRÌNH KẾT THÚC.")


if __name__ == "__main__":
    main()