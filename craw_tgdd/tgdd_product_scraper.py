import os
import time
import logging
import re
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(40)
    return driver


def click_load_more(driver, max_clicks=10):
    clicks = 0
    for _ in range(max_clicks):
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 600);")
            time.sleep(2)
            # Selector cho nút Xem thêm của TGDĐ
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.view-more a, .cart-more a, a.view-more")))
            driver.execute_script("arguments[0].click();", btn)
            clicks += 1
            logging.info(f"    Click 'Xem thêm' lần {clicks}...")
            time.sleep(3)
        except:
            break
    return clicks


def extract_products(driver, category):
    products = []
    items = driver.find_elements(By.CSS_SELECTOR, "ul.listproduct li.item")
    for item in items:
        try:
            link_tag = item.find_element(By.CSS_SELECTOR, "a.main-contain")
            p_id = item.get_attribute("data-id") or link_tag.get_attribute("data-id")
            p_name = link_tag.get_attribute("data-name") or item.find_element(By.CSS_SELECTOR, "h3").text.strip()
            p_url = link_tag.get_attribute("href")

            if p_id and p_name:
                products.append({
                    "product_id": p_id,
                    "product_name": p_name,
                    "product_url": p_url,
                    "category": category
                })
        except:
            continue
    return products


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    categories = {
        "Laptop": "https://www.thegioididong.com/laptop",
        "Smartphone": "https://www.thegioididong.com/dtdd",
        "Tablet": "https://www.thegioididong.com/may-tinh-bang",
        "Monitor": "https://www.thegioididong.com/man-hinh-may-tinh",
        "Desktop": "https://www.thegioididong.com/may-tinh-de-ban",
        "BluetoothHeadphone": "https://www.thegioididong.com/tai-nghe-bluetooth",
        "Headphone": "https://www.thegioididong.com/tai-nghe-chup-tai"
    }

    os.makedirs("tgdd_links", exist_ok=True)
    driver = get_driver()

    for cat, url in categories.items():
        full_url = f"{url}#o=7&pi=0"
        logging.info(f"Đang cào danh mục: {cat}")
        driver.get(full_url)
        time.sleep(4)

        click_load_more(driver, max_clicks=8)
        prods = extract_products(driver, cat)

        df = pd.DataFrame(prods)
        df.to_csv(f"tgdd_links/{cat.lower()}_products.csv", index=False, encoding='utf-8-sig')
        logging.info(f"Xong {cat}: {len(prods)} sản phẩm.")

    driver.quit()


if __name__ == "__main__":
    main()