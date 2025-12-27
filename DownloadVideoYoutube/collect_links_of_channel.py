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
            logging.FileHandler("data_bonbanh/scraper_per_links_bonbanh 0_1519.log", encoding='utf-8'),
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

def surf_until_end(channel_link):
    driver = None
    driver = get_chrome_driver()

    return