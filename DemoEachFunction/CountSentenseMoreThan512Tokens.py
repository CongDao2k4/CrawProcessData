import pandas as pd

df = pd.read_csv('../CrawVTV/data_vtv/processed/all_vtv.csv')
cnt = 0
for i in range(len(df)):
    original_content = df.at[i, 'content']
    # Ví dụ: thêm dấu chấm than
    text = original_content

    # Bước 1: tách câu theo dấu chấm
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    print(len(sentences))
    for sentence in sentences:
        if len(sentence.split()) > 218:
            print(f'hàng {i} có cau > 218 chữ')
            print(len(sentence))
