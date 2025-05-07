import hashlib
import pandas as pd
import toml
import os

# Pepper を .streamlit/secrets.toml から読み込む
secrets = toml.load(os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml'))
pepper = secrets['auth']['pepper']

# フォーム回答 CSV を読み込み
# 列名を実際のフォームに合わせて指定
df = pd.read_csv('form_responses_final.csv', dtype=str)
df['student_id'] = df['学生番号'].str.lstrip('0')
df = df.drop_duplicates(subset='student_id', keep='last')

rows = []
for _, row in df.iterrows():
    sid = row['学生番号']
    pwd = row['パスワード']
    if pd.isna(pwd) or pwd == '':
        continue
    # SHA256(password + pepper)
    hash_hex = hashlib.sha256((pwd + pepper).encode('utf-8')).hexdigest()
    role = 'admin' if sid == '22' else 'student'
    rows.append({
        'student_id': sid,
        'password_hash': hash_hex,
        'role': role
    })

# auth.csv を生成
auth_df = pd.DataFrame(rows, columns=['student_id', 'password_hash', 'role'])
auth_df.to_csv('auth.csv', index=False)
print('✅ auth.csv を生成しました')
