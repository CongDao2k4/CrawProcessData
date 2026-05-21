import os
import time
import logging
import re
import sys
import json
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def init_logging():
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler("dienmayxanh_integrated_scraper.log", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

def get_chrome_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

def clean_price(raw: str) -> str:
    """'15.990.000đ' -> '15990000'"""
    if not raw:
        return ""
    return re.sub(r'[^\d]', '', raw)

def clean_sold(raw: str) -> str:
    """'• Đã bán 3,7k' -> '3700' (ước lượng)"""
    if not raw:
        return ""
    raw = raw.replace("•", "").replace("Đã bán", "").strip()
    raw = raw.replace(",", ".")
    m = re.search(r'([\d.]+)\s*k', raw, re.IGNORECASE)
    if m:
        return str(int(float(m.group(1)) * 1000))
    m2 = re.search(r'\d+', raw)
    return m2.group(0) if m2 else ""

def build_full_url(href: str) -> str:
    """Chuẩn hóa URL tuyệt đối"""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    return "https://www.dienmayxanh.com" + href

def save_batch_to_csv(data_list: list, output_file: str):
    """Lưu 1 batch vào CSV và lọc trùng theo product_id"""
    if not data_list:
        return
    df_new = pd.DataFrame(data_list)
    # Lưu categories dạng JSON string
    df_new['categories'] = df_new['categories'].apply( lambda x: json.dumps(x, ensure_ascii=False) )

    if os.path.exists(output_file) and os.stat(output_file).st_size > 0:
        try:
            existing_ids = pd.read_csv( output_file, usecols=['product_id'], dtype={'product_id': str} )['product_id'].unique()
            df_new = df_new[~df_new['product_id'].isin(existing_ids)]
        except Exception as e:
            logging.error(f"        [Loi loc trung] {str(e)}")
    if df_new.empty:
        logging.info("        - Khong co san pham moi nao trong me nay (da trung).")
        return
    try:
        file_exists = os.path.exists(output_file) and os.stat(output_file).st_size > 0
        df_new.to_csv(
            output_file, mode='a', index=False,
            header=not file_exists, encoding='utf-8-sig'
        )
        logging.info(f"        Da luu me {len(df_new)} san pham vao {os.path.basename(output_file)}")
    except Exception as e:
        logging.error(f"        LOI GHI FILE: {str(e)}")

def click_load_more(driver, max_clicks: int = 10) -> int:
    clicks = 0
    # Selector cụ thể dựa trên HTML bạn vừa gửi
    target_selectors = [
        "strong.see-more-btn",
        ".view-more a",
        "a.view-more"
    ]
    for _ in range(max_clicks):
        try:
            # 1. Cuộn xuống để nút lọt vào tầm nhìn (viewport)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 600);")
            time.sleep(2)
            btn = None
            for sel in target_selectors:
                try:
                    # Tìm tất cả element khớp selector
                    elements = driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elements:
                        if e.is_displayed():
                            btn = e
                            break
                    if btn: break
                except:
                    continue
            if not btn:
                logging.info(f"    [Dừng] Không tìm thấy nút Xem thêm (đã click {clicks} lần).")
                break
            # 2. Đưa nút vào giữa màn hình để tránh bị thanh Header che khuất
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            # 3. Click bằng JavaScript (Cách này luôn chạy được kể cả khi bị thẻ khác đè lên)
            driver.execute_script("arguments[0].click();", btn)
            clicks += 1
            logging.info(f"    [Thành công] Click 'Xem thêm' lần {clicks}...")
            # 4. Chờ AJAX load dữ liệu (DMX thường load khá chậm, nên để 3-4s)
            time.sleep(3.5)
        except Exception as e:
            logging.warning(f"    Lỗi phát sinh khi click: {str(e)[:50]}")
            break
    return clicks

def extract_product_cards(driver, base_category_list: list) -> list:
    products = []
    seen_ids = set()

    # 1. Chờ danh sách sản phẩm xuất hiện (Dùng selector tổng quát nhất)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.listproduct li.item"))
        )
    except TimeoutException:
        logging.warning("    [Lỗi] Không tìm thấy danh sách sản phẩm sau khi load.")
        return products

    # 2. Lấy tất cả các thẻ li có class 'item'
    items = driver.find_elements(By.CSS_SELECTOR, "ul.listproduct li.item")
    logging.info(f"    Tìm thấy {len(items)} thẻ sản phẩm. Đang bóc tách dữ liệu...")

    for item in items:
        try:
            # Bỏ qua nếu là banner quảng cáo xen kẽ
            if "banner" in item.get_attribute("class"):
                continue

            # 3. LẤY DỮ LIỆU TỪ ATTRIBUTE CỦA THẺ <a> (Chính xác và sạch nhất)
            # Thẻ a.main-contain chứa đầy đủ metadata_amazon
            try:
                link_tag = item.find_element(By.CSS_SELECTOR, "a.main-contain")
            except NoSuchElementException:
                continue

            # Lấy thông tin từ các thuộc tính data-
            product_id = link_tag.get_attribute("data-id") or item.get_attribute("data-id")
            product_name = link_tag.get_attribute("data-name") # Tên sạch 100%
            price_current = link_tag.get_attribute("data-price")
            product_url = build_full_url(link_tag.get_attribute("href") or "")

            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            # 4. LẤY ẢNH (Xử lý Lazy Load)
            image_url = ""
            try:
                img = item.find_element(By.CSS_SELECTOR, ".item-img img")
                # DMX dùng data-src cho lazy load, nếu chưa load thì lấy src
                image_url = img.get_attribute("data-src") or img.get_attribute("src") or ""
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
            except:
                pass

            # 5. LẤY GIÁ CŨ & GIẢM GIÁ (Nếu có)
            price_old = ""
            discount_pct = ""
            try:
                price_old_tag = item.find_element(By.CSS_SELECTOR, ".price-old")
                price_old = clean_price(price_old_tag.text)
                discount_tag = item.find_element(By.CSS_SELECTOR, ".percent")
                discount_pct = discount_tag.text
            except:
                pass

            # 6. LẤY RATING & ĐÃ BÁN
            rating = ""
            sold_count = ""
            try:
                rating = item.find_element(By.CSS_SELECTOR, ".vote-txt b").text.strip()
                sold_raw = item.find_element(By.CSS_SELECTOR, ".rating_Compare span").text
                sold_count = clean_sold(sold_raw)
            except:
                pass

            # Chỉ lưu khi có đủ ID và Tên
            if product_id and product_name:
                products.append({
                    'product_id':    product_id,
                    'product_name':  product_name,
                    'product_url':   product_url,
                    'image_url':     image_url,
                    'price_current': clean_price(str(price_current)),
                    'price_old':     price_old,
                    'discount_pct':  discount_pct,
                    'rating':        rating,
                    'sold_count':    sold_count,
                    'categories':    base_category_list,
                    'source':        'dienmayxanh.com',
                })

        except Exception as e:
            # logging.debug(f"Lỗi thẻ: {str(e)}")
            continue

    return products
# ============================================================
#  XU LY 1 URL (dieu huong -> click Xem them -> cao -> luu)
# ============================================================
def process_listing_url(driver, cat_name: str, brand_name: str,
                         base_url: str, sort_hash: str,
                         output_file: str, max_load_more: int):
    """
    Luong chinh: chi o trang listing, KHONG di vao trang detail.
    1. Dieu huong toi URL + hash filter Ban Chay
    2. Click 'Xem them' nhieu lan de tai toan bo san pham
    3. Cao card san pham
    4. Luu vao CSV
    """
    full_url = base_url + sort_hash
    base_category_list = [cat_name, brand_name]

    logging.info(f"\n  [{brand_name}] Dieu huong: {full_url}")
    driver.get(full_url)
    time.sleep(4)  # Cho JS & AJAX render

    # Click "Xem them" toi da max_load_more lan
    total_clicks = click_load_more(driver, max_clicks=max_load_more)
    logging.info(f"  [{brand_name}] Da click 'Xem them' tong cong {total_clicks} lan.")

    # Cao tat ca card hien co tren DOM
    products = extract_product_cards(driver, base_category_list)
    logging.info(f"  [{brand_name}] Cao duoc {len(products)} san pham.")

    if products:
        save_batch_to_csv(products, output_file)

# ============================================================
#  HAM CHAY CHINH
# ============================================================
def run_dienmayxanh_scraper(categories_config: dict,
                             output_dir: str = 'dmx_links',
                             max_load_more: int = 8):
    """
    Chay scraper cho toan bo categories.
    categories_config:
        { "Category": { "Brand": { "url": ..., "hash": ... } } }
    """
    init_logging()
    os.makedirs(output_dir, exist_ok=True)
    driver = get_chrome_driver()

    try:
        for cat_name, brands_data in categories_config.items():
            safe_name = cat_name.replace(' ', '_').lower()
            output_file = os.path.join(output_dir, f"{safe_name}_integrated.csv")

            logging.info(f"\n{'='*60}")
            logging.info(f"BAT DAU DANH MUC: {cat_name.upper()}")
            logging.info(f"{'='*60}")

            for brand_name, url_info in brands_data.items():
                try:
                    process_listing_url(
                        driver,
                        cat_name=cat_name,
                        brand_name=brand_name,
                        base_url=url_info['url'],
                        sort_hash=url_info.get('hash', '#o=7&pi=0'),
                        output_file=output_file,
                        max_load_more=max_load_more,
                    )
                except Exception as e:
                    logging.error(f"  LOI brand '{brand_name}': {str(e)}")

                time.sleep(3)  # Nghi nho giua cac brand

    finally:
        driver.quit()
        logging.info("\nHOAN TAT TOAN BO QUA TRINH CAO DIEN MAY XANH.")


# ============================================================
#  CAU HINH CATEGORIES & CHAY
# ============================================================
# NOTE: hash #o=7&pi=0  => Bo loc "Ban chay nhat" cua Dien May Xanh
#       pi=0       => Bat dau tu trang 1
# ============================================================
if __name__ == '__main__':
    categories_config = {
        "Laptop": {
            "Apple": {
                "url":  "https://www.dienmayxanh.com/laptop-apple",
                "hash": "#o=7&pi=0"
            },
            "Dell": {
                "url":  "https://www.dienmayxanh.com/laptop-dell",
                "hash": "#o=7&pi=0"
            },
            "HP": {
                "url":  "https://www.dienmayxanh.com/laptop-hp",
                "hash": "#o=7&pi=0"
            },
            "Lenovo": {
                "url":  "https://www.dienmayxanh.com/laptop-lenovo",
                "hash": "#o=7&pi=0"
            },
            "Asus": {
                "url":  "https://www.dienmayxanh.com/laptop-asus",
                "hash": "#o=7&pi=0"
            },
            "Acer": {
                "url":  "https://www.dienmayxanh.com/laptop-acer",
                "hash": "#o=7&pi=0"
            },
            "MSI": {
                "url":  "https://www.dienmayxanh.com/laptop-msi",
                "hash": "#o=7&pi=0"
            },
        },

        "Smartphone": {
            "Apple": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-apple",
                "hash": "#o=7&pi=0"
            },
            "Samsung": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-samsung",
                "hash": "#o=7&pi=0"
            },
            "Xiaomi": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-xiaomi",
                "hash": "#o=7&pi=0"
            },
            "Oppo": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-oppo",
                "hash": "#o=7&pi=0"
            },
            "Vivo": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-vivo",
                "hash": "#o=7&pi=0"
            },
            "Realme": {
                "url":  "https://www.dienmayxanh.com/dien-thoai-realme",
                "hash": "#o=7&pi=0"
            },
        },

        "PC": {
            "Dell": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-dell",
                "hash": "#o=7&pi=0"
            },
            "HP": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-hp",
                "hash": "#o=7&pi=0"
            },
            "Lenovo": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-lenovo",
                "hash": "#o=7&pi=0"
            },
            "Asus": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-asus",
                "hash": "#o=7&pi=0"
            },
            "MSI": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-msi",
                "hash": "#o=7&pi=0"
            },
            "Acer": {
                "url":  "https://www.dienmayxanh.com/may-tinh-nguyen-bo-acer",
                "hash": "#o=7&pi=0"
            },
        },

        "Television": {
            "Samsung": {
                "url":  "https://www.dienmayxanh.com/tivi-samsung",
                "hash": "#o=7&pi=0"
            },
            "LG": {
                "url":  "https://www.dienmayxanh.com/tivi-lg",
                "hash": "#o=7&pi=0"
            },
            "Sony": {
                "url":  "https://www.dienmayxanh.com/tivi-sony",
                "hash": "#o=7&pi=0"
            },
            "Panasonic": {
                "url":  "https://www.dienmayxanh.com/tivi-panasonic",
                "hash": "#o=7&pi=0"
            },
            "TCL": {
                "url":  "https://www.dienmayxanh.com/tivi-tcl",
                "hash": "#o=7&pi=0"
            },
            "Hisense": {
                "url":  "https://www.dienmayxanh.com/tivi-hisense",
                "hash": "#o=7&pi=0"
            },
        },

        "Headphone": {
            "Apple": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-apple",
                "hash": "#o=7&pi=0"
            },
            "Sony": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-sony",
                "hash": "#o=7&pi=0"
            },
            "Samsung": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-samsung",
                "hash": "#o=7&pi=0"
            },
            "JBL": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-jbl",
                "hash": "#o=7&pi=0"
            },
            "Jabra": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-jabra",
                "hash": "#o=7&pi=0"
            },
            "Bose": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-bose",
                "hash": "#o=7&pi=0"
            },
            "Xiaomi": {
                "url":  "https://www.dienmayxanh.com/tai-nghe-xiaomi",
                "hash": "#o=7&pi=0"
            },
        },
    }

    run_dienmayxanh_scraper(
        categories_config,
        output_dir='dmx_links',
        max_load_more=8,   # So lan click "Xem them" toi da moi trang
    )
