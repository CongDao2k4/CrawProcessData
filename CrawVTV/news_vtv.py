import csv
import re

import requests
import pandas as pd
import time
import random
import os
import json
from datetime import datetime

from bs4 import BeautifulSoup
from tqdm import tqdm
import logging
import sys

from DemoEachFunction import demoTakeLinkPerPage

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper_vtvgo.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class NewsScraperVTV:
    def __init__(self, output_dir="data_vtv"):
        self.output_dir = output_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://vtv.vn/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        self.session = requests.Session()
        try:
            # Tạo thư mục đầu ra nếu chưa tồn tại
            os.makedirs(output_dir, exist_ok=True)
            for subdir in ["raw", "processed"]:
                os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)
        except Exception as e:
            logging.error(f"Lỗi khi tạo thư mục: {str(e)}")
            sys.exit(1)

    def scrape_vtv(self, num_pages):
        """Thu thập dữ liệu từ vtv"""
        logging.info("Bắt đầu thu thập dữ liệu từ VTV")
        article_links = []

        categories = [
            "chinh-tri","xa-hoi", "phap-luat", "the-gioi", "kinh-te", "the-thao", "truyen-hinh",
            "van-hoa-giai-tri", "doi-song", "cong-nghe", "giao-duc"
        ]

        try:
            response = self.session.get("https://vtv.vn", timeout=10, headers=self.headers)
            if response.status_code != 200:
                logging.error(f"Không thể kết nối đến VTV: Mã trạng thái {response.status_code}")
                return None
            logging.info("Kết nối thành công đến vtv.vn")
        except requests.exceptions.RequestException as e:
            logging.error(f"Không thể kết nối đến VTV: {str(e)}")
            return None

        for category in categories:
            try:
                url_to_try = f"https://vtv.vn/{category}.htm"
                logging.info(f"Đang thử truy cập: {url_to_try}")

                response = self.session.get(url_to_try, headers=self.headers, timeout=15)
                if response.status_code != 200:
                    logging.warning(f"Không thể truy cập trang {url_to_try}, mã trạng thái: {response.status_code}")
                    continue

                logging.info(f"Truy cập thành công: {url_to_try}")

                options = Options()
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")

                driver = webdriver.Chrome(options=options)
                driver.get(url_to_try)
                time.sleep(15)

                last_height = driver.execute_script("return document.body.scrollHeight")

                for _ in range(10):
                    # Cuộn xuống cuối trang
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(8)

                    # Thử click vào nút "Xem thêm" nếu có
                    try:
                        xem_them = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Xem thêm')]"))
                        )
                        driver.execute_script("arguments[0].scrollIntoView(true);", xem_them)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", xem_them)
                        time.sleep(2)
                    except:
                        pass  # Không thấy hoặc không click được nút

                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height

                # Lấy tất cả liên kết bài viết
                articles = driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class,'list__new-bot')]//div[contains(@class,'box-col-left')]//div[contains(@class,'col-')]//a[@href]"
                )
                links = [a.get_attribute('href') for a in articles if a.get_attribute('href').endswith('.htm')]
                driver.quit()

                links_not_http = list(set(links))
                if not links_not_http:
                    logging.warning(f"Không thu thập được liên kết nào từ chuyên mục {category}")
                    continue
                for href in links_not_http:
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            href = f"https://vtv.vn{href}"
                        else:
                            href = f"https://vtv.vn/{href}"
                    if not any(item['url'] == href for item in article_links):
                        article_links.append({
                            'url': href,
                            'source': 'vtv',
                            'category': category
                        })

                logging.info(f"Đã thu thập {len(article_links)} liên kết từ vtv - chuyên mục {category}")
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                logging.error(f"Lỗi khi thu thập liên kết từ chuyên mục {category}: {str(e)}")
                time.sleep(random.uniform(5, 10))

        # Loại bỏ liên kết trùng
        unique_links = []
        unique_urls = set()
        for link in article_links:
            if link['url'] not in unique_urls:
                unique_urls.add(link['url'])
                unique_links.append(link)

        logging.info(f"Tổng số liên kết duy nhất: {len(unique_links)}")
        self._claim_content(unique_links)

    def _save_links_to_csv(self, links, filename="article_links.csv"):
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(self.output_dir, exist_ok=True)
            file_path = os.path.join(self.output_dir, filename)
            file_exists = os.path.exists(file_path)  # Kiểm tra xem file có tồn tại không
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['url', 'source', 'category']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()  # Chỉ ghi header nếu file mới
                for link in links:
                    writer.writerow(link)
            logging.info(f"Đã lưu các liên kết vào file: {file_path}")
        except Exception as e:
            logging.error(f"Lỗi khi lưu vào file CSV: {str(e)}")

    def _claim_content(self, unique_links):
        number_of_claim_article = 0
        for article_info in tqdm(unique_links, desc="Thu thập bài viết vtv"):
            try:
                article_data = self._scrape_vtv_article(article_info['url'], article_info['category'])
                if article_data:
                    number_of_claim_article += 1
                    # Lưu dữ liệu thô
                    self._save_raw_article(article_data)
                    time.sleep(random.uniform(1, 3))
            except Exception as e:
                logging.error(f"Lỗi khi thu thập bài viết từ {article_info['url']}: {str(e)}")
        logging.info(f"Đã hoàn thành thu thập dữ liệu từ VTV: {number_of_claim_article} bài viết")

    def _scrape_vtv_article(self, url, category):
        """Thu thập thông tin từ một bài viết vtv"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = self.session.get(url, headers=self.headers, timeout=15)
                if response.status_code != 200:
                    logging.warning(f"Không thể truy cập {url}, mã trạng thái: {response.status_code}")
                    retry_count += 1
                    time.sleep(random.uniform(2, 5))
                    continue
                # Cạo dữ liệu 1 link Web bài viết cụ thể
                response.encoding = 'utf-8'  # Đảm bảo encoding đúng
                soup = BeautifulSoup(response.text, 'html.parser')
                detail_summary = soup.find('div', class_='noidung').find('h2', class_='sapo').get_text().strip()
                detail_content = soup.find('div', class_='noidung').find('div', class_='ta-justify').get_text().strip()
                #print(detail_summary)
                #print(detail_content)

                return {
                    'category': category,
                    'url': url,
                    'source': 'vtv',
                    'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'summary': detail_summary,
                    'content': detail_content
                }
            except requests.exceptions.RequestException as e:
                retry_count += 1
                logging.warning(f"Lỗi kết nối khi thu thập bài viết (lần {retry_count}/{max_retries}): {url}")
                if retry_count == max_retries:
                    logging.error(f"Lỗi khi thu thập bài viết sau {max_retries} lần thử: {url}")
                    return None
                time.sleep(random.uniform(3, 6))
            except Exception as e:
                logging.error(f"Lỗi không xác định khi xử lý bài viết {url}: {str(e)}")
                return None
        return None

    def _save_raw_article(self, article_data):
        """Lưu dữ liệu thô của một bài viết"""
        try:
            filename = f"{article_data['source']}_{int(time.time())}_{article_data['category']}.json"
            with open(os.path.join(self.output_dir, "raw", filename), 'w', encoding='utf-8') as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Lỗi khi lưu dữ liệu thô: {str(e)}")

    def preprocess_data(self):
        """Tiền xử lý dữ liệu đã thu thập"""
        logging.info("Bắt đầu tiền xử lý dữ liệu")
        fail = 0
        try:
            data = self.load_raw_data()
            processed_data = []
            for article in tqdm(data, desc="Tiền xử lý dữ liệu"):
                processed_article = self.clean_article(article)
                if processed_article:
                    fail += 1
                    processed_data.append(processed_article)

            # Lưu dữ liệu đã xử lý
            df = pd.DataFrame(processed_data)
            df.to_csv(os.path.join(self.output_dir, "processed", "vtv_article.csv"), index=False, encoding='utf-8')

            logging.info(f"Đã hoàn thành tiền xử lý dữ liệu: {len(processed_data)} bài viết")
            logging.info(f"Đã hỏng tiền xử lý dữ liệu: {fail} bài viết")
            return len(processed_data)
        except Exception as e:
            logging.error(f"Lỗi trong quá trình tiền xử lý dữ liệu: {str(e)}")
            return []

    def load_raw_data(self):
        """Đọc dữ liệu thô từ thư mục raw"""
        logging.info("Đọc dữ liệu thô từ thư mục")
        data = []
        raw_dir = os.path.join(self.output_dir, "raw")
        num=0
        for filename in os.listdir(raw_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(raw_dir, filename), 'r', encoding='utf-8') as f:
                        num += 1
                        article_data = json.load(f)
                        data.append(article_data)
                except Exception as e:
                    logging.error(f"Lỗi khi đọc file {filename}: {str(e)}")
        logging.info(f"Đã đọc {len(data)} bài viết từ thư mục raw")
        logging.info(f"đọc {num} file json")
        return data

    def clean_article(self, article):
        try:
            if not all(k in article for k in ['url', 'summary', 'content']):
                logging.info("thiếu url, summ, content")
                return None
            summary = self.clean_text(article['summary'])
            content = self.clean_text(article['content'])

            if not summary or not content or len(content.split()) < 50:
                return None

            if not summary:
                content_words = content.split()
                summary = ' '.join(content_words[:min(50, len(content_words))])

            cleaned_article = {
                'url': article['url'],
                'summary': summary,
                'content': content,
            }
            return cleaned_article
        except Exception as e:
            logging.error(f"Lỗi khi làm sạch bài viết: {str(e)}")
            return None
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'(?<=[^\.\?\!])\n+', '. ', text)
        text = re.sub(r'(?<=[\.\?\!])\n+', ' ', text)
        text = re.sub(r'[“”"]', '', text)
        text = re.sub(r'\(Ảnh:.*?\)', '', text)
        text = re.sub(r'^VTV\.vn\s*-\s*', '', text)
        text = re.sub(r'\*.*?VTVGo.*?\.\s*\Z', '', text, flags=re.MULTILINE)
        text = re.sub(r'VTV\.\s?vn', 'VTV.vn', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def run_scraper(self, target_count=2000, pages_per_source=100):
        start_time = time.time()
        logging.info(f"Bắt đầu quá trình thu thập dữ liệu với mục tiêu {target_count} bài viết")
        self.scrape_vtv(num_pages=pages_per_source)
        end_time = time.time()
        logging.info(f"Đã hoàn thành toàn bộ quá trình trong {(end_time - start_time) / 60:.2f} phút")

if __name__ == "__main__":
    try:
        '''
        # Kiểm tra Python version
        if sys.version_info[0] < 3:
            raise Exception("Yêu cầu Python 3 trở lên")

        # Kiểm tra thư viện
        required_packages = ['requests', 'beautifulsoup4', 'pandas', 'tqdm', 'underthesea']
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            print(f"Vui lòng cài đặt các thư viện sau: {', '.join(missing_packages)}")
            print("Sử dụng lệnh: pip install -r requirements.txt")
            sys.exit(1)
        '''
        scraper = NewsScraperVTV()
        # scraper.run_scraper(target_count=50, pages_per_source=10)
        scraper.preprocess_data()
    except KeyboardInterrupt:
        print("\nĐã dừng chương trình theo yêu cầu của người dùng")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Lỗi không xác định: {str(e)}")
        sys.exit(1)
