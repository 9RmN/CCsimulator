#!/usr/bin/env python3
import os
import json
import hashlib
import pandas as pd
import subprocess
from google.auth import default
from googleapiclient.discovery import build

# --- 環境変数 & st.secrets から Pepper 取得 ---
try:
    import streamlit as st
    PEPPER = st.secrets["auth"]["pepper"]
    print("ℹ️ PEPPER を st.secrets から読み込みました")
except Exception:
    PEPPER = os.environ.get("PEPPER")
    if PEPPER:
        print("ℹ️ PEPPER を環境変数から読み込みました")

# --- SPREADSHEET_ID のチェック ---
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise RuntimeError("環境変数 SPREADSHEET_ID が設定されていません。")

# --- シート範囲設定 ---
RANGE_NAME = os.environ.get("RANGE_NAME", "'フォームの回答'!A1:AZ1000")

# --- Google API 認証 ---
creds, _ = default(scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
service = build("sheets", "v4", credentials=creds)

# --- Step 1: フォーム回答取得 ---
print("📥 Googleフォーム回答を取得中...")
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=RANGE_NAME
).execute()
values = result.get("values", [])
if not values:
    print("❌ データが取得できませんでした")
    exit(1)
# ヘッダー列数に合わせて各行をパディング or 切り詰め
header = values[0]
rows = values[1:]
ncol = len(header)
aligned = []
for row in rows:
    if len(row) < ncol:
        aligned.append(row + [""] * (ncol - len(row)))
    else:
        aligned.append(row[:ncol])
df = pd.DataFrame(aligned, columns=header)
df.to_csv("form_responses_final.csv", index=False)
print("✅ form_responses_final.csv を保存しました")

# --- Step 2: responses.csv 生成 ---
print("🔄 responses.csv に変換中...")
try:
    df2 = pd.read_csv("form_responses_final.csv", dtype=str)

    # グリッド質問の列名マッピング (第n希望 → "希望ターム [第n希望]")
    term_columns = {
        i: f"希望ターム [第{i}希望]"
        for i in range(1, 21)
        if f"希望ターム [第{i}希望]" in df2.columns
    }

    output = {
        "student_id": df2.iloc[:, 1].str.lstrip("0"),
        "password":   df2.iloc[:, 2]
    }

    for i in range(1, 21):
        # 科目の読み取り（既存ロジック）
        hcol = i * 2 + 1
        dcol = i * 2 + 2
        try:
            hosp = df2.iloc[:, hcol].fillna("")
            dept = df2.iloc[:, dcol].fillna("")
            combined = (hosp + "-" + dept).str.strip().replace("", pd.NA)
        except Exception:
            combined = pd.NA
        output[f"hope_{i}"] = combined

        # グリッド回答からターム番号を取り出し
        grid_col = term_columns.get(i)
        if grid_col:
            raw = df2[grid_col].fillna("")            # 例: "3ターム"
            # 数字部分だけ抽出して Int 型に
            term_num = raw.str.extract(r"^(\d+)")[0].astype("Int64")
            output[f"hope_{i}_term"] = term_num
        else:
            output[f"hope_{i}_term"] = pd.NA

    # DataFrame 化＋重複削除
    responses = pd.DataFrame(output)
    before = len(responses)
    responses = responses.drop_duplicates(subset="student_id", keep="last")
    deleted = before - len(responses)
    print(f"✅ 重複排除: {deleted} 件削除, 残り {len(responses)} 件")

    # CSV 出力
    responses.to_csv("responses.csv", index=False)
    print("✅ responses.csv を生成しました")
except Exception as e:
    print("❌ responses.csv への変換に失敗:", e)
    exit(1)

# --- Step 3: auth.csv 生成（PEPPER 必要） ---
if PEPPER:
    print("🔐 auth.csv を生成中…")
    auth_src = pd.read_csv("form_responses_final.csv", dtype=str)
    auth_src["student_id"] = auth_src["学生番号"].str.lstrip("0")
    auth_src = auth_src.drop_duplicates(subset="student_id", keep="last")
    rows = []
    for _, row in auth_src.iterrows():
        sid = row["student_id"]
        pwd = row.get("パスワード", "")
        if pd.isna(pwd) or pwd == "":
            continue
        hash_hex = hashlib.sha256((pwd + PEPPER).encode("utf-8")).hexdigest()
        role = "admin" if sid == "22" else "student"
        rows.append({"student_id": sid, "password_hash": hash_hex, "role": role})
    auth_df = pd.DataFrame(rows, columns=["student_id", "password_hash", "role"])
    auth_df.to_csv("auth.csv", index=False)
    print("✅ auth.csv を生成しました")
else:
    print("⚠️ PEPPER が設定されていないため auth.csv をスキップします")

# --- Step 4: その他スクリプト実行 ---
scripts = [
    "initial_assignment.py",
    "simulate_with_unanswered.py",
    "generate_probability.py",
    "generate_popular_rank.py",
    "analyze_assignment.py",
    "analyze_department.py"
]

for script in scripts:
    if script == "generate_probability.py":
        print(f"⚙️ {script} をデフォルト呼び出し（20 iterations）で実行中…")
        subprocess.run(["python", script], check=True)
    elif script == "simulate_with_unanswered.py":
        print(f"⚙️ {script} をサイレント実行中…")
        subprocess.run(
            ["python", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    else:
        print(f"⚙️ {script} を実行中…")
        subprocess.run(["python", script], check=True)

print("\n✅ 全パイプライン実行完了！")
