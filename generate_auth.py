# generate_auth.py

import os
import hashlib
import pandas as pd

# デバッグ用：環境変数・ファイルの存在をログ出力
print("🔍 DEBUG generate_auth.py start")
print("ENV PEPPER:", os.environ.get("PEPPER"))
print("Exists form_responses_final.csv?", os.path.exists("form_responses_final.csv"))

# CI では環境変数 PEPPER、Cloud では st.secrets
try:
    pepper = os.environ["PEPPER"]
    print("Using PEPPER from env")
except KeyError:
    import streamlit as st
    pepper = st.secrets["PEPPER"]
    print("Using PEPPER from st.secrets")

try:
    # フォーム回答 CSV を読み込み
    print("Reading form_responses_final.csv...")
    df = pd.read_csv("form_responses_final.csv", dtype=str)
except Exception as e:
    print("❌ Failed to read form_responses_final.csv:", e)
    raise

df["student_id"] = df["student_id"].str.lstrip("0")
df = df.drop_duplicates(subset="student_id", keep="last")

rows = []
for _, row in df.iterrows():
    sid = row.get("student_id", "")
    pwd = row.get("password", "")  # フォームのカラム名に合わせてください
    if pd.isna(pwd) or pwd == "":
        continue
    hash_hex = hashlib.sha256((pwd + pepper).encode("utf-8")).hexdigest()
    role = "admin" if sid == "22" else "student"
    rows.append({"student_id": sid, "password_hash": hash_hex, "role": role})

auth_df = pd.DataFrame(rows, columns=["student_id", "password_hash", "role"])
auth_df.to_csv("auth.csv", index=False)
print("✅ auth.csv を生成しました")
