import datetime
import sys
import re
import requests
from bs4 import BeautifulSoup


def craw1web_of_vneconomy(response):
    response.encoding = 'utf-8'  # Đảm bảo encoding đúng
    soup = BeautifulSoup(response.text, 'html.parser')
    detail_summary = soup.find('h2', class_='detail__summary')
    detail_content = soup.find('div', class_='detail__content')
    print(detail_summary.text)
    print(detail_content.text)
    return [detail_summary.get_text(), detail_content.get_text()]
def craw1web_of_vtv(response):
    response.encoding = 'utf-8'  # Đảm bảo encoding đúng
    soup = BeautifulSoup(response.text, 'html.parser')
    detail_summary = soup.find('div', class_ = 'noidung').find('h2', class_ = 'sapo').get_text().strip()
    detail_content = soup.find('div', class_='noidung').find('div',class_='ta-justify').get_text().strip()
    print(detail_summary)
    print(detail_content)
    return [detail_summary, detail_content]

if __name__ == '__main__':
    #craw1web_of_vneconomy(requests.get('https://vneconomy.vn/bo-ngoai-giao-quyet-dinh-ap-thue-quan-cua-my-voi-hang-hoa-viet-nam-chua-phu-hop-voi-thuc-te-hop-tac-giua-hai-nuoc.htm'))
    craw1web_of_vtv(requests.get('https://vtv.vn/xa-hoi/csgt-ha-noi-kip-thoi-xu-ly-vet-dau-loang-tren-cau-dam-bao-an-toan-cho-nguoi-di-duong-20250505153756209.htm'))