# generate_auth.py

import os
import hashlib
import pandas as pd

# CI では環境変数 PEPPER、Cloud では st.secrets
pepper = os.environ["PEPPER"]
if not pepper:
    import streamlit as st
    pepper = st.secrets["PEPPER"]

# フォーム回答 CSV を読み込み
df = pd.read_csv("form_responses_final.csv", dtype=str)
df["student_id"] = df["student_id"].str.lstrip("0")
df = df.drop_duplicates(subset="student_id", keep="last")

rows = []
for _, row in df.iterrows():
    sid = row["student_id"]
    pwd = row["password"]  # フォームのカラム名に合わせて
    if pd.isna(pwd) or pwd == "":
        continue
    hash_hex = hashlib.sha256((pwd + pepper).encode("utf-8")).hexdigest()
    role = "admin" if sid == "22" else "student"
    rows.append({"student_id": sid, "password_hash": hash_hex, "role": role})

auth_df = pd.DataFrame(rows, columns=["student_id", "password_hash", "role"])
auth_df.to_csv("auth.csv", index=False)
print("✅ auth.csv を生成しました")
