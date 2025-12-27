import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def craw_links_per_page_of_vneconomy(response):
    # htmlpage = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    soup = soup.find(class_='zone zone--featured')
    # Lấy tất cả các thẻ <a> và trích xuất href
    links = [a['href'] for a in soup.find_all('a', href=True)]
    filtered_links = [link for link in links if link.endswith('.htm')]
    unique_links = list(set(filtered_links))
    return unique_links

def demoTakeLinkPerPage(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(5)

    last_height = driver.execute_script("return document.body.scrollHeight")

    for _ in range(5):
        # Cuộn xuống cuối trang
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

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

    return list(set(links))  # Loại trùng


if __name__ == '__main__':
    # unique_links = craw_links_per_page_of_vneconomy(requests.get('https://vneconomy.vn/dia-oc.htm?trang=27'))
    unique_links = demoTakeLinkPerPage("https://vtv.vn/chinh-tri.htm")
    print(len(unique_links))
    print(*unique_links, sep='\n')
