import csv
import time

import pandas as pd
import requests
import os
import logging
import sys
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

def init(output_dir='data_bonbanh'):
    # Thiết lập logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("scraper_per_links_bonbanh.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    try:
        os.makedirs(output_dir, exist_ok=True)
        for subdir in ["raw", "processed"]:
            os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)
    except Exception as e:
        logging.error(f"Lỗi khi tạo thư mục: {str(e)}")
        sys.exit(1)


def get_chrome_driver():
    """Hàm khởi tạo và cấu hình Chrome driver"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(50)
    return driver


def check_url_with_requests(url_to_try):
    """Kiểm tra URL có khả dụng không bằng requests"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://bonbanh.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }

    session = requests.Session()
    try:
        response = session.get(url_to_try, timeout=50, headers=headers)
        if response.status_code != 200:
            logging.error(f"    Không thể kết nối đến {url_to_try} : Mã trạng thái {response.status_code}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"    Không thể kết nối đến {url_to_try} : {str(e)}")
        return False
    finally:
        session.close()


def verify_page_content(driver, url_to_try):
    """Kiểm tra nội dung trang có đầy đủ không"""
    try:
        if driver.current_url != url_to_try:
            logging.warning(f"    {url_to_try} sai lệch nên web đã trở về trang chủ https://bonbanh.com ")
            return False

        wait = WebDriverWait(driver, 50)
        xpath_trigger_1 = "//div[@id='car_detail']//div[@class='title']"
        xpath_trigger_2 = "//div[@id='car_detail']//div[@id='sgg']"
        xpath_trigger_3 = "//div[@id='car_detail']//div[@class='contact-box']//div[@class='cinfo']//div[@class='contact-txt']"

        wait.until(EC.all_of(
            EC.presence_of_element_located((By.XPATH, xpath_trigger_1)),
            EC.presence_of_element_located((By.XPATH, xpath_trigger_2)),
            EC.presence_of_element_located((By.XPATH, xpath_trigger_3))
        ))  # Chỉ cần nó có trong DOM

        # wait.until(EC.all_of(
        #     EC.visibility_of_element_located(By.XPATH, xpath_trigger_1),
        #     EC.visibility_of_element_located(By.XPATH, xpath_trigger_2),
        #     EC.visibility_of_element_located(By.XPATH, xpath_trigger_3)
        # )) # Đợi đến khi đảm bảo nó hiển thị trên trang

        logging.info(f"    Truy cập thành công {url_to_try} !")
        return True
    except Exception as ex:
        import traceback
        logging.warning(f"    Lỗi do thông tin không đầy đủ khi truy cập {url_to_try}: {type(ex).__name__} - {str(ex)}")
        logging.debug(traceback.format_exc())
        return False


def checkAcceptable(url_to_try, driver):
    # Bước 1: Kiểm tra nhanh bằng requests
    if not check_url_with_requests(url_to_try):
        return 0
    # Bước 2: Kiểm tra chi tiết bằng Selenium
    try:
        driver.get(url_to_try)
        if verify_page_content(driver, url_to_try):
            return 1
        return 0
    except Exception as ex:
        import traceback
        logging.warning(f"    Lỗi không xác định khi kiểm tra {url_to_try}: {type(ex).__name__} - {str(ex)}")
        logging.debug(traceback.format_exc())
        return 0


def crawl_per_car(list_of_links):
    """
    Thu thập dữ liệu từ danh sách links
    Tối ưu: Chỉ khởi tạo driver 1 lần cho toàn bộ danh sách
    """
    infos = []
    driver = None

    try:
        # Khởi tạo driver 1 lần duy nhất
        driver = get_chrome_driver()

        for link in list_of_links:
            url_to_try = link
            logging.info(f"Đang thử truy cập {url_to_try}")

            # Sử dụng lại driver đã khởi tạo
            status = checkAcceptable(url_to_try, driver)
            logging.info(f"    Status là {status}")

            if status == 0:
                continue

            try:
                # Không cần khởi tạo driver mới, trang đã được load trong checkAcceptable
                wait = WebDriverWait(driver, 50)

                css_trigger_1 = "div#car_detail > div.title"
                css_trigger_2 = "div#car_detail > div#sgg"
                css_trigger_3 = "div#car_detail > div.contact-box > div.cinfo > div.contact-txt"

                wait.until(EC.all_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, css_trigger_1)),
                    EC.presence_of_element_located((By.CSS_SELECTOR, css_trigger_2)),
                    EC.presence_of_element_located((By.CSS_SELECTOR, css_trigger_3))
                ))

                css_selector_name = "div#car_detail > div.title > h1"
                css_selector_sell_time = "div#car_detail > div.title > div.notes"
                css_selector_info = "div#car_detail > div#sgg"
                css_selector_contact = "div#car_detail > div.contact-box > div.cinfo > div.contact-txt"

                info_per_car = extract_each_attributes(
                    css_selector_name,
                    css_selector_sell_time,
                    css_selector_info,
                    css_selector_contact,
                    driver
                )
                infos.append(info_per_car)

            except Exception as e:
                logging.warning(f"    Lỗi không xác định khi trích xuất thông từ {url_to_try} - Lỗi chi tiết: {str(e)}")

            time.sleep(5)

    finally:
        # Đảm bảo driver được đóng sau khi xử lý hết danh sách
        if driver:
            driver.quit()

    save_links_to_csv(infos)

# def extract_each_attributes(css_selector_name, css_selector_sell_time, css_selector_info, css_selector_contact, driver):
#     logging.info(f"    Bắt đầu lấy các thông tin của xe {driver.current_url}")
#     dct = dict.fromkeys(['name','sell_time','produce_year','current_status','traveled_kilometer','origin',
#                           'shape','gear_box','engine','out_color','in_color','seat_number','door_number','dynamic_axes',
#                           'describe_info','owner_name','phone_number_1','phone_number_2','owner_address'])
#
#     dct['name'] = driver.find_element(By.CSS_SELECTOR, css_selector_name).text
#     dct['sell_time'] = driver.find_element(By.CSS_SELECTOR, css_selector_sell_time).text
#
#     info = driver.find_element(By.CSS_SELECTOR, css_selector_info)
#     spans = info.find_elements(By.CSS_SELECTOR, "div.row > div.txt_input > span.inp")
#     texts = [span.text.strip() for span in spans]
#     fields = [
#         'produce_year', 'current_status', 'traveled_kilometer', 'origin',
#         'shape', 'gear_box', 'engine', 'out_color', 'in_color',
#         'seat_number', 'door_number', 'dynamic_axes'
#     ]
#     for i, field in enumerate(fields):
#         dct[field] = texts[i] if i < len(texts) else None
#     dct['describe_info'] = info.find_element(By.CSS_SELECTOR, "div.car_des > div.des_txt").text
#
#     contact = driver.find_element(By.CSS_SELECTOR, css_selector_contact)
#
#     # Cố gắng tìm cả 2 loại thẻ (a hoặc span) có class cname
#     owner_elem = driver.find_elements(By.CSS_SELECTOR, "a.cname, span.cname")
#     if not owner_elem:
#         logging.warning(f"    Không tìm thấy thẻ .cname cho tên người bán tại {driver.current_url}")
#     dct['owner_name'] = owner_elem[0].text.strip() if owner_elem else None
#
#     phones = contact.find_elements(By.CSS_SELECTOR, "span.cphone > a.cphone")
#     dct['phone_number_1'], dct['phone_number_2'] = ([None, None] + [phone.text.strip() for phone in phones])[-2:]
#     address_lines = contact.text.split('\n')
#     dct['owner_address'] = address_lines[-1].strip() if address_lines else None
#
#     print(json.dumps(dct, ensure_ascii=False, indent=2))
#     return dct


def safe_find_text(driver, selector):
    """Hàm hỗ trợ: tìm phần tử, nếu không có thì trả về None"""
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text.strip()
    except NoSuchElementException:
        return None


def extract_each_attributes(css_selector_name, css_selector_sell_time, css_selector_info, css_selector_contact, driver):
    logging.info(f"    Bắt đầu lấy các thông tin của xe {driver.current_url}")

    dct = dict.fromkeys([
        'name', 'sell_time', 'produce_year', 'current_status', 'traveled_kilometer', 'origin',
        'shape', 'gear_box', 'engine', 'out_color', 'in_color', 'seat_number', 'door_number', 'dynamic_axes',
        'describe_info', 'owner_name', 'phone_number_1', 'phone_number_2', 'owner_address'
    ])

    # Tên xe và thời gian đăng bán
    dct['name'] = safe_find_text(driver, css_selector_name)
    dct['sell_time'] = safe_find_text(driver, css_selector_sell_time)

    # Map nhãn (đã chuyển thường hết)
    mapping = {
        "năm sản xuất": "produce_year",
        "tình trạng": "current_status",
        "số km đã đi": "traveled_kilometer",
        "xuất xứ": "origin",
        "kiểu dáng": "shape",
        "hộp số": "gear_box",
        "động cơ": "engine",
        "màu ngoại thất": "out_color",
        "màu nội thất": "in_color",
        "số chỗ ngồi": "seat_number",
        "số cửa": "door_number",
        "dẫn động": "dynamic_axes"
    }

    try:
        info = driver.find_element(By.CSS_SELECTOR, css_selector_info)
        rows = info.find_elements(By.CSS_SELECTOR, "div.row, div.row_last")

        for row in rows:
            try:
                label_el = row.find_element(By.CSS_SELECTOR, "div.label")
                label = label_el.text.strip().replace(":", "").lower().strip()
                try:
                    # Trường hợp có <span class="inp">
                    value_el = row.find_element(By.CSS_SELECTOR, "div.txt_input > span.inp, div.inputbox > span.inp")
                    value = value_el.text.strip()
                except NoSuchElementException:
                    # Không có span, lấy text trực tiếp từ div.txt_input
                    try:
                        box_el = row.find_element(By.CSS_SELECTOR, "div.txt_input, div.inputbox")
                        value = box_el.text.strip()
                    except NoSuchElementException:
                        value = None

                if label in mapping:
                    dct[mapping[label]] = value if value else None
            except Exception:
                continue
    except NoSuchElementException:
        pass
    # Đảm bảo đủ 12 key
    for key in mapping.values():
        dct[key] = dct.get(key, None)

    # Mô tả
    try:
        dct['describe_info'] = info.find_element(By.CSS_SELECTOR,"div.car_des > div.des_txt").text.strip() if info else None
    except NoSuchElementException:
        dct['describe_info'] = None

    # Thông tin liên hệ
    try:
        contact = driver.find_element(By.CSS_SELECTOR, css_selector_contact)
    except NoSuchElementException:
        contact = None

    # Tên người bán (a.cname hoặc span.cname)
    try:
        owner_elem = contact.find_elements(By.CSS_SELECTOR, "a.cname, span.cname") if contact else []
        dct['owner_name'] = owner_elem[0].text.strip() if owner_elem else None
    except Exception:
        dct['owner_name'] = None

    # Số điện thoại
    try:
        phones = contact.find_elements(By.CSS_SELECTOR, "span.cphone > a.cphone") if contact else []
        phone_texts = [p.text.strip() for p in phones if p.text.strip()]
        dct['phone_number_2'], dct['phone_number_1'] = ([None, None] + phone_texts)[-2:]
    except Exception:
        dct['phone_number_2'], dct['phone_number_1'] = None, None

    # Địa chỉ
    try:
        if contact:
            address_lines = [line.strip() for line in contact.text.split('\n') if line.strip()]
            found_address = None
            for line in address_lines:
                lower_line = line.lower()
                if "địa chỉ" in lower_line or "dia chi" in lower_line:
                    found_address = line.strip()
                    break
            dct['owner_address'] = found_address
        else:
            dct['owner_address'] = None

    except Exception as e:
        logging.debug(f"Lỗi khi lấy địa chỉ: {e}")
        dct['owner_address'] = None

    print(json.dumps(dct, ensure_ascii=False))#''', indent=2'''))
    return dct


def save_links_to_csv(infos, filename="info_cars.csv", output_dir='data_bonbanh'):
    try:
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir,'raw', filename)
        file_exists = os.path.exists(file_path)

        with open(file_path, 'a+', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['name','sell_time','produce_year','current_status','traveled_kilometer','origin',
                          'shape','gear_box','engine','out_color','in_color','seat_number','door_number','dynamic_axes',
                          'describe_info','owner_name','phone_number_1','phone_number_2','owner_address']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()  # chỉ ghi header nếu file mới
            for info in infos:
                writer.writerow(info)
        logging.info(f"Đã lưu thêm {len(infos)} liên kết vào file: {file_path}")
    except Exception as e:
        logging.error(f"Lỗi khi lưu vào file CSV: {str(e)}")

# if __name__ == '__main__':
#     init()
#     lst_links = ['https://bonbanh.com/xe-mg-hs-1.5t-del-2025-6457197', 'https://bonbanh.com/xe-bmw-5_series-530i-m-sport-2022-6190459', 'https://bonbanh.com/xe-toyota-prado-vx-2.7l-2021-6367137']
#     crawl_per_car(lst_links)

def load_urls_from_csv(csv_path):
    """Đọc file CSV chứa danh sách URL."""
    if not os.path.exists(csv_path):
        logging.error(f"❌ File {csv_path} không tồn tại!")
        return []

    try:
        df = pd.read_csv(csv_path)
        if 'url' not in df.columns:
            logging.error("❌ File CSV không có cột 'url'!")
            return []
        urls = df['url'].dropna().tolist()
        logging.info(f"✅ Đọc được {len(urls)} URL từ {csv_path}")
        return urls
    except Exception as e:
        logging.error(f"❌ Lỗi khi đọc file CSV {csv_path}: {e}")
        return []

def main():
    init()
    csv_path = os.path.join("data_bonbanh", "sell_cars.csv")

    lst_links = load_urls_from_csv(csv_path)
    if not lst_links:
        logging.warning("⚠️ Không có URL nào để crawl.")
        return

    for i in range(1520,2000,10):
        logging.info(f"ĐANG CẠO LINK ROW {i} đến {i+9}")
        crawl_per_car(lst_links[i:i+10])  # Gọi hàm crawl như cũ

if __name__ == "__main__":
    main()
