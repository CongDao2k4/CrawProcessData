import csv
import time

import requests
import os
import logging
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def init(output_dir='data_bonbanh'):
    # Thiết lập logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("scraper_bonbanh.log", encoding='utf-8'),
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
        'Referer': 'https://bonbanh.com/oto/',
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
        # logging.info(f"Kết nối thành công đến {url_to_try}")
        # return True
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"    Không thể kết nối đến {url_to_try} : {str(e)}")
        return False
    finally:
        if session is not None:
            session.close()


def verify_pagination(driver, url_to_try):
    """
    Kiểm tra phân trang
    Return: 0 = lỗi, 1 = có thêm trang, 2 = trang cuối
    """
    # logging.info(f"    URL hiện tại là: {driver.current_url}")
    if driver.current_url != url_to_try:
        logging.warning(f"    {url_to_try} sai lệch nên web đã trở về trang chủ https://bonbanh.com ")
        return 0

    try:
        wait = WebDriverWait(driver, 50)
        xpath_selector = "//div[@class='pagging']//div[@class='navpage']//div[@class='navpage']//span[@class='bbl' and contains(text(), '>>')]"  # chirir cần span.bll có nội dung = >>
        # xpath_selector = "//div[@class='pagging']//div[@class='navpage']//div[@class='navpage']//span[@class='bbl'][last()]"  # hoặc tìm span.bll cuối cùng trong các span của navpage
        wait.until(EC.presence_of_element_located((By.XPATH, xpath_selector)))  # Chỉ cần nó có trong DOM
        # wait.until(EC.visibility_of_element_located((By.XPATH, xpath_selector)))  # Đợi đến khi đảm bảo nó hiển thị trên trang
        logging.info(f"    Truy cập thành công {url_to_try} !")
        return 1
    except:
        logging.warning("    Không tìm thấy nút >> để chuyển đến trang cuối -> tức là đã đến trang page cuối cùng !")
        return 2


def checkAcceptable(url_to_try, driver):
    """
    Kiểm tra URL có hợp lệ không
    Return: 0 = lỗi, 1 = có thêm trang, 2 = trang cuối
    """
    if not check_url_with_requests(url_to_try):
        return 0
    try:
        driver.get(url_to_try)
        return verify_pagination(driver, url_to_try)
    except Exception as ex:
        logging.warning(f"    Lỗi không xác định khi kiểm tra {url_to_try}: {type(ex).__name__} - {str(ex)}")
        return 0

def extract_car_links(driver, url_to_try):
    """Trích xuất danh sách links xe từ trang"""
    try:
        wait = WebDriverWait(driver, 50)
        css_trigger = "div#search_content > div.gray-box > div.g-box-content > ul"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_trigger)))

        css_selector = "div#search_content > div.gray-box > div.g-box-content > ul > li > a[itemprop='url']"
        car_links = []

        link_elements = driver.find_elements(By.CSS_SELECTOR, css_selector)
        if not link_elements:
            logging.warning("    Không tìm thấy phần tử liên kết xe nào trên trang này.")
            return car_links
        for element in link_elements:
            href = element.get_attribute("href")
            # logging.info(f"    Link trích xuất: {href}")
            if href:
                car_links.append(href)
        logging.info(f"    >>> Đã trích xuất thành công {len(car_links)} liên kết xe.")
        return car_links

    except Exception as e:
        logging.warning(
            f"    Lỗi không tìm được các links bài đăng khi trích xuất liên kết ở trang {url_to_try} : {str(e)}")
        return []


def surf_web_per_page(start_page, end_page):
    links = set()
    driver = None

    try:
        # Khởi tạo driver 1 lần duy nhất
        driver = get_chrome_driver()
        for page in range(start_page, end_page + 1):
            url_to_try = 'https://bonbanh.com/oto/' + 'page,' + str(page)
            logging.info(f"Đang thử truy cập {url_to_try}")
            status = checkAcceptable(url_to_try, driver)
            logging.info(f"    Status là {status}")

            if status == 0:
                continue
            try:
                car_links = extract_car_links(driver, url_to_try)
                links.update(car_links)
            except Exception as e:
                logging.warning(f"    Lỗi không xác định khi trích xuất liên kết: {str(e)}")

            time.sleep(5)
            if status == 2:
                break
    finally:
        if driver is not None:
            driver.close()

    save_links_to_csv(links)

def save_links_to_csv(links, filename="sell_cars.csv", output_dir='data_bonbanh'):
    try:
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)
        file_exists = os.path.exists(file_path)

        with open(file_path, 'a+', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()  # chỉ ghi header nếu file mới
            for link in links:
                writer.writerow({'url': link})  # ✅ bọc chuỗi thành dict

        logging.info(f"Đã lưu thêm {len(links)} liên kết vào file: {file_path}")
    except Exception as e:
        logging.error(f"Lỗi khi lưu vào file CSV: {str(e)}")


if __name__ == '__main__':
    init()
    # surf_web_per_page(1,5)
    # surf_web_per_page(6, 10)
    # surf_web_per_page(11, 15)
    # surf_web_per_page(16, 20)
    # surf_web_per_page(21, 25)
    # surf_web_per_page(26, 30)
    # surf_web_per_page(31,50)
    # surf_web_per_page(51,70)
    # surf_web_per_page(71,90)
    # surf_web_per_page(91,110)
    # surf_web_per_page(111,130)
    # surf_web_per_page(131,150)
    # surf_web_per_page(151,200)
    # surf_web_per_page(201,230)
    # surf_web_per_page(231,260)
    # surf_web_per_page(261,300)
    surf_web_per_page(301,330)


