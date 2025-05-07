import os
import json
import hashlib
import pandas as pd

# Pepper は必ず環境変数から取得
PEPPER = os.environ.get("PEPPER")
if not PEPPER:
    raise RuntimeError("環境変数 PEPPER が設定されていません。")

# Google フォーム回答 CSV
df = pd.read_csv("form_responses_final.csv", dtype=str)
# 列名が「学生番号」「パスワード」の場合
df["student_id"] = df["学生番号"].str.lstrip("0")
df = df.drop_duplicates(subset="student_id", keep="last")

rows = []
for _, row in df.iterrows():
    sid = row["student_id"]
    pwd = row["パスワード"]
    if pd.isna(pwd) or pwd == "":
        continue
    hash_hex = hashlib.sha256((pwd + PEPPER).encode("utf-8")).hexdigest()
    role = "admin" if sid == "22" else "student"
    rows.append({
        "student_id":    sid,
        "password_hash": hash_hex,
        "role":          role
    })

auth_df = pd.DataFrame(rows, columns=["student_id","password_hash","role"])
auth_df.to_csv("auth.csv", index=False)
print("✅ auth.csv を生成しました")
