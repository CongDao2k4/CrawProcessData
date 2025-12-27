import json
import logging
import os
import re
from datetime import time
from random import random

import pandas as pd
from tqdm import tqdm


def preprocess_data():
    """Tiền xử lý dữ liệu đã thu thập"""
    logging.info("Bắt đầu tiền xử lý dữ liệu")

    try:
        data = load_raw_data()
        processed_data = []
        for article in tqdm(data, desc="Tiền xử lý dữ liệu"):
            processed_article = clean_article(article)
            if processed_article:
                processed_data.append(processed_article)

        # Lưu dữ liệu đã xử lý
        df = pd.DataFrame(processed_data)
        df.to_csv(os.path.join("../CrawVNEconomy/data", "processed", "all_vtv.csv"), index=False, encoding='utf-8')

        logging.info(f"Đã hoàn thành tiền xử lý dữ liệu: {len(processed_data)} bài viết")
        return len(processed_data)
    except Exception as e:
        logging.error(f"Lỗi trong quá trình tiền xử lý dữ liệu: {str(e)}")
        return []


def load_raw_data():
    """Đọc dữ liệu thô từ thư mục raw"""
    logging.info("Đọc dữ liệu thô từ thư mục")
    data = []
    raw_dir = os.path.join("../CrawVTV/data_vtv", "raw")

    for filename in os.listdir(raw_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(raw_dir, filename), 'r', encoding='utf-8') as f:
                    article_data = json.load(f)
                    data.append(article_data)
            except Exception as e:
                logging.error(f"Lỗi khi đọc file {filename}: {str(e)}")
    logging.info(f"Đã đọc {len(data)} bài viết từ thư mục raw")
    return data

def clean_article(article):
    """Làm sạch dữ liệu của một bài viết"""
    try:
        # Kiểm tra dữ liệu có đầy đủ không
        if not all(k in article for k in ['url', 'summary', 'content']):
            return None
        # Loại bỏ các ký tự HTML và ký tự đặc biệt
        summary = clean_text(article['summary'])
        content = clean_text(article['content'])

        # Kiểm tra dữ liệu sau khi làm sạch
        if not summary or not content or len(content.split()) < 50:
            return None
        # Nếu tóm tắt trống, tạo tóm tắt từ đoạn đầu của nội dung
        if not summary:
            content_words = content.split()
            summary = ' '.join(content_words[:min(50, len(content_words))])

        # Tạo bài viết đã được làm sạch
        cleaned_article = {
            'url': article['url'],
            'summary': summary,
            'content': content,
        }
        return cleaned_article
    except Exception as e:
        logging.error(f"Lỗi khi làm sạch bài viết: {str(e)}")
        return None


def clean_text(text):
    """Làm sạch văn bản"""
    if not text:
        return ""

    # Thay \n đứng một mình hoặc có nhiều khoảng trắng thành dấu chấm (nếu chưa có dấu câu phía trước)
    #text = re.sub(r'(?<=[^\.\?\!])\n+', '. ', text)  # Thêm dấu chấm nếu trước \n không có dấu câu
    # Nếu đã có dấu chấm trước \n thì chỉ thay \n bằng khoảng trắng
    #text = re.sub(r'(?<=[\.\?\!])\n+', ' ', text)
    # Loại bỏ dấu nháy kép
    #text = re.sub(r'[“”"]', '', text)

    # 1. Vẫn xoá các đoạn (Ảnh: ...), thường không cần thiết
    #text = re.sub(r'\(Ảnh:.*?\)', '', text)
    # 2. Chỉ xoá phần "VTV.vn -" ở đầu, giữ lại nội dung phía sau
    #text = re.sub(r'^VTV\.vn\s*-\s*', '', text)  # Dấu ^ đảm bảo chỉ xử lý nếu ở dòng đầu
    # 3. Cẩn trọng khi xoá các dòng kiểu quảng bá
    # Dùng \Z để chỉ tìm ở cuối
    #text = re.sub(r'\*.*?VTVGo.*?\.\s*\Z', '', text, flags=re.MULTILINE)
    # 4. Xử lý "VTV. vn" thành "VTV.vn" thay vì xóa
    #text = re.sub(r'VTV\.\s?vn', 'VTV.vn', text)

    # 1. Thay thế các dấu câu khác thành dấu chấm
    text = re.sub(r'[?!…;]+', '.', text)
    # 2. Xử lý xuống dòng thành dấu chấm nếu trước đó không có dấu câu
    text = re.sub(r'(?<=[^\.\n])\n+', '. ', text)  # nếu trước \n không có dấu chấm thì thêm
    text = re.sub(r'(?<=[\.])\n+', ' ', text)  # nếu trước \n đã có dấu chấm thì thay bằng khoảng trắng
    # 3. Xoá dấu nháy kép
    text = re.sub(r'[“”"]', '', text)
    # 4. Xoá các đoạn không cần thiết
    text = re.sub(r'\(Ảnh:.*?\)', '', text)
    text = re.sub(r'^VTV\.vn\s*-\s*', '', text)
    text = re.sub(r'\*.*?VTVGo.*?\.\s*\Z', '', text, flags=re.MULTILINE)
    text = re.sub(r'VTV\.\s?vn', 'VTV.vn', text)
    # 5. Gộp các dấu chấm liên tiếp lại thành 1
    text = re.sub(r'\.{2,}', '.', text)
    # Xoá khoảng trắng dư thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return FitToShorter256Token(text)
def FitToShorter256Token(text):
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    text = ""
    result = []
    for sentence in sentences:
        if len(sentence.split()) <= 128:
            result.append(sentence)
        else:
            # Nếu câu dài hơn max_len, tách tiếp theo dấu phẩy
            parts = [p.strip() for p in sentence.split(',')]
            temp = ""
            for part in parts:
                l = len(part.split())

                if len(temp.split()) + l + 1 <= 128:
                    # cộng phần này vào temp, thêm dấu phẩy nếu temp ko rỗng
                    if temp != "":
                        temp += ', ' + part
                    else:
                        temp = part
                else:
                    # temp đạt giới hạn, lưu lại và bắt đầu temp mới
                    if temp != "":
                        result.append(temp)
                    words = part.split()
                    for i in range(0, len(words), 128):
                        for j in range(i, min(i + 128, len(words))):
                            temp = temp + words[j] + ' '
                        result.append(temp)
                        temp = ""
                    temp = ""
            # Lưu phần cuối cùng
            if temp != "":
                result.append(temp)
    for s in result:
        text = text + s + '. '
    return text

if __name__ == '__main__':
    preprocess_data()
    '''with open('data/raw/vneconomy_1743939046_tieu-diem.json', 'r', encoding='utf-8') as f:
        article_data = json.load(f)
        print(article_data['content'])
        cleaned_data = clean_article(article_data)
        print(cleaned_data['url'])
        print(cleaned_data['summary'])
        print(cleaned_data['content'])'''
    '''df = pd.read_csv('../data_vtv/processed/vtv_article.csv')
    cnt = 0
    for i in range(len(df)):
        original_content = df.at[i, 'content']
        # Ví dụ: thêm dấu chấm than
        text = original_content

        # Bước 1: tách câu theo dấu chấm
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        text = ""

        result = []
        for sentence in sentences:
            if len(sentence.split()) <= 128:
                result.append(sentence)
            else:
                cnt += 1
                # Nếu câu dài hơn max_len, tách tiếp theo dấu phẩy
                parts = [p.strip() for p in sentence.split(',')]
                temp = ""
                for part in parts:
                    l = len(part.split())

                    if len(temp.split()) + l + 1 <= 128:
                        # cộng phần này vào temp, thêm dấu phẩy nếu temp ko rỗng
                        if temp != "":
                            temp += ', ' + part
                        else:
                            temp = part
                    else:
                        # temp đạt giới hạn, lưu lại và bắt đầu temp mới
                        if temp != "":
                            result.append(temp)
                        else :
                            words = part.split()
                            for i in range(0,len(words),128):
                                for j in range(i,min(i+128,len(words))):
                                    temp = temp + words[j] + ' '
                                result.append(temp)
                                temp=""
                        temp = ""
                # Lưu phần cuối cùng
                if temp != "":
                    result.append(temp)
        for s in result:
            text = text + s + '. '

        df.at[i, 'content'] = text
    df.to_csv(os.path.join("../data_vtv", "processed", "all_vtv.csv"), index=False, encoding='utf-8')
    print(f'có {cnt} hàng thay đổi')'''

