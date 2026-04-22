import os
import time
import json
import re
import logging
import random
import sys
import pandas as pd
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchWindowException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# --- Cấu hình Logging ---
def init_logging():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler("tgdd_full_crawl_v4.log", encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("🚀 Hệ thống cào TGDD v4 (Trang gốc + Pages) sẵn sàng.")


def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--incognito")  # Dùng ẩn danh để tránh lưu session lỗi

    # 1. KHÔNG dùng các dòng này với undetected-chromedriver:
    # options.add_experimental_option("excludeSwitches", ["enable-automation"]) <-- XÓA DÒNG NÀY
    # options.add_argument("--disable-blink-features=AutomationControlled") <-- UC ĐÃ TỰ LÀM RỒI

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    # driver = webdriver.Chrome(options=options)
    # driver.set_page_load_timeout(60)
    # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver = uc.Chrome(options=options, version_main=146)
    driver.set_page_load_timeout(40)

    return driver

def parse_relative_time(time_str):
    now = datetime.now()
    match = re.search(r'(\d+)', time_str)
    n = int(match.group(1)) if match else 1

    if "giây" in time_str or "phút" in time_str:
        min_diff, max_diff = timedelta(minutes=1), timedelta(minutes=n + 1)
    elif "giờ" in time_str:
        min_diff, max_diff = timedelta(hours=n), timedelta(hours=n + 1)
    elif "ngày" in time_str:
        min_diff, max_diff = timedelta(days=n), timedelta(days=n + 1)
    elif "tuần" in time_str:
        min_diff, max_diff = timedelta(days=n * 7), timedelta(days=(n + 1) * 7)
    elif "tháng" in time_str:
        min_diff, max_diff = timedelta(days=n * 30), timedelta(days=(n + 1) * 30)
    else:
        min_diff, max_diff = timedelta(days=1), timedelta(days=2)

    random_seconds = random.randint(int(min_diff.total_seconds()), int(max_diff.total_seconds()))
    target_date = now - timedelta(seconds=random_seconds)
    return target_date.replace(hour=random.randint(0, 23), minute=random.randint(0, 59),
                               second=random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S")


# --- Hàm bóc tách Review dùng chung cho cả trang gốc và trang page ---
def parse_review_elements(elements):
    parsed_data = []
    for it in elements:
        try:
            name = it.find_element(By.CSS_SELECTOR, ".cmt-top-name").text.strip()
            stars = len(it.find_elements(By.CSS_SELECTOR, ".cmt-top-star i.iconcmt-starbuy"))
            content = it.find_element(By.CSS_SELECTOR, ".cmt-content p.cmt-txt").text.strip()
            time_el = it.find_elements(By.CSS_SELECTOR, ".cmtd")
            time_raw = time_el[0].text.strip().replace("Đã dùng khoảng ", "") if time_el else "1 ngày trước"

            parsed_data.append({
                "fullName": name,
                "rating": stars,
                "content": content,
                "creationTime": parse_relative_time(time_raw)
            })
        except:
            continue
    return parsed_data


# --- Bước 1: Lấy Metadata và Review tại trang gốc ---
def get_metadata_and_initial_reviews(driver, url, fallback_id):
    try:
        driver.get(url)
        time.sleep(random.uniform(3, 5))
        wait = WebDriverWait(driver, 25)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.breadcrumb")))

        # 1. Metadata
        nodes = driver.find_elements(By.CSS_SELECTOR, "ul.breadcrumb li a, ul.breadcrumb li h2 a")
        breadcrumb = " > ".join([n.text.strip() for n in nodes if n.text.strip()])
        try:
            real_id = driver.find_element(By.CSS_SELECTOR, "section.detail").get_attribute("data-id")
        except:
            real_id = fallback_id
        try:
            p_name = driver.find_element(By.CSS_SELECTOR, "section.detail h1").text.strip()
        except:
            p_name = ""

        meta = {"id": real_id, "name": p_name, "breadcrumb": breadcrumb}

        # 2. Review tại trang gốc (nếu có)
        initial_reviews = []
        try:
            # Cuộn xuống khu vực rating để kích hoạt load review
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            review_elements = driver.find_elements(By.CSS_SELECTOR, "ul.comment-list li.par")
            initial_reviews = parse_review_elements(review_elements)
            logging.info(f"      ✅ Tìm thấy {len(initial_reviews)} review tại trang gốc.")
        except:
            pass

        return meta, initial_reviews
    except Exception as e:
        logging.error(f"❌ Lỗi truy cập trang gốc {url}: {e}")
        return None, []


# --- Bước 2: Cào review ở trang page=x ---
def extract_reviews_from_page(driver, url):
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 25)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.comment-list li.par")))

        if "captcha" in driver.current_url.lower(): return "RESTART"

        items = driver.find_elements(By.CSS_SELECTOR, "ul.comment-list li.par")
        if not items: return None

        return parse_review_elements(items)
    except:
        return None


def main():
    init_logging()
    input_dir, output_dir = "tgdd_links", "tgdd_reviews"
    os.makedirs(output_dir, exist_ok=True)

    driver = get_driver()
    processed_count = 0

    for file in os.listdir(input_dir):
        if not file.endswith(".csv"): continue
        df = pd.read_csv(os.path.join(input_dir, file))
        out_file = os.path.join(output_dir, file.replace(".csv", ".jsonl"))

        for idx, row in df.iterrows():
            processed_count += 1
            if processed_count % 10 == 0:
                driver.quit()
                driver = get_driver()

            base_url = row['product_url']
            p_id_fallback = str(row['product_id'])

            # 1. TRANG GỐC: Lấy Metadata + Review ban đầu
            meta, initial_reviews = None, []
            for attempt in range(3):
                try:
                    logging.info(f"🔍 [{processed_count}] Đang xử lý: {base_url}")
                    meta, initial_reviews = get_metadata_and_initial_reviews(driver, base_url, p_id_fallback)
                    if meta: break
                except (WebDriverException, NoSuchWindowException, TimeoutException):
                    driver.quit()
                    driver = get_driver()

            if not meta: continue

            all_product_reviews = []
            seen_content = set()  # Chống trùng review

            # Gộp review từ trang gốc
            for r in initial_reviews:
                signature = f"{r['fullName']}_{r['content'][:50]}"  # Ký hiệu chống trùng
                if signature not in seen_content:
                    seen_content.add(signature)
                    r.update({"productId": meta["id"], "productName": meta["name"], "breadcrumb": meta["breadcrumb"]})
                    all_product_reviews.append(r)

            # 2. CÁC TRANG DANH GIA (Page 1 -> n)
            review_base_url = f"{base_url.split('?')[0].rstrip('/')}/danh-gia"
            page, not_found_count = 1, 0

            while not_found_count < 3:  # Để 3 cho nhanh, nếu muốn kỹ hãy để 5
                target_url = f"{review_base_url}?page={page}"
                logging.info(f"   📑 Page {page} -> {target_url}")

                result = extract_reviews_from_page(driver, target_url)

                if result == "RESTART":
                    driver.quit()
                    driver = get_driver()
                    continue

                if result:
                    not_found_count = 0
                    added_count = 0
                    for r in result:
                        signature = f"{r['fullName']}_{r['content'][:50]}"
                        if signature not in seen_content:
                            seen_content.add(signature)
                            r.update({"productId": meta["id"], "productName": meta["name"],
                                      "breadcrumb": meta["breadcrumb"]})
                            all_product_reviews.append(r)
                            added_count += 1

                    logging.info(f"      ✅ Thêm {added_count} review mới.")

                    if len(all_product_reviews) >= 20:
                        with open(out_file, "a", encoding="utf-8") as f:
                            for r in all_product_reviews: f.write(json.dumps(r, ensure_ascii=False) + "\n")
                        all_product_reviews = []
                else:
                    not_found_count += 1
                    logging.warning(f"      ⚠️ Trống (Lần {not_found_count}/3)")

                page += 1
                time.sleep(random.uniform(1.0, 2.0))

            # Lưu số dư cuối cùng
            if all_product_reviews:
                with open(out_file, "a", encoding="utf-8") as f:
                    for r in all_product_reviews: f.write(json.dumps(r, ensure_ascii=False) + "\n")
            logging.info(f"✨ Hoàn tất SP: {meta['id']}")

    driver.quit()


if __name__ == "__main__":
    main()