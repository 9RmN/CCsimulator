# generate_auth.py

import os
import sys
import traceback
import hashlib
import pandas as pd

def main():
    # デバッグ用ログ
    print("🔍 DEBUG generate_auth.py start")
    print("ENV PEPPER:", os.environ.get("PEPPER"))
    print("Exists form_responses_final.csv?", os.path.exists("form_responses_final.csv"))

    # PEPPER取得
    pepper = os.environ.get("PEPPER")
    if not pepper:
        # Cloud 用 fallback（ほとんど CI では通りませんが一応）
        import streamlit as st
        pepper = st.secrets["PEPPER"]
        print("Using PEPPER from st.secrets")
    else:
        print("Using PEPPER from env")

    # CSV 読み込み
    print("Reading form_responses_final.csv...")
    df = pd.read_csv("form_responses_final.csv", dtype=str)

    # ノーマライズ
    df["student_id"] = df["student_id"].str.lstrip("0")
    df = df.drop_duplicates(subset="student_id", keep="last")

    # ハッシュ生成
    rows = []
    for _, row in df.iterrows():
        sid = row.get("student_id", "")
        pwd = row.get("password", "")
        if pd.isna(pwd) or pwd == "":
            continue
        hash_hex = hashlib.sha256((pwd + pepper).encode()).hexdigest()
        role = "admin" if sid == "22" else "student"
        rows.append({"student_id": sid, "password_hash": hash_hex, "role": role})

    # 出力
    auth_df = pd.DataFrame(rows, columns=["student_id", "password_hash", "role"])
    auth_df.to_csv("auth.csv", index=False)
    print("✅ auth.csv を生成しました")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("❌ Exception in generate_auth.py:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
