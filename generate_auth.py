# generate_auth.py

import os
import sys
import hashlib
import pandas as pd
import traceback

def fatal(msg):
    """エラー時にメッセージを出力して終了"""
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    # --- 1) PEPPER の取得 ---
    pepper = os.getenv("PEPPER")
    if not pepper:
        fatal("環境変数 PEPPER が設定されていません。GitHub Actions の env に secrets.PEPPER を渡してください。")
    print("✅ PEPPER loaded from environment")

    # --- 2) CSV 読み込み ---
    csv_path = "form_responses_final.csv"
    if not os.path.exists(csv_path):
        fatal(f"{csv_path} が存在しません。最新のフォーム回答を取得してください。")
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        fatal(f"{csv_path} の読み込みに失敗しました: {e}")
    print(f"✅ Loaded {csv_path} ({len(df)} rows)")

    # --- 3) 正規化 & 重複削除 ---
    if "student_id" in df.columns:
        sid_col = "student_id"
    elif "学生番号" in df.columns:
        sid_col = "学生番号"
    else:
        fatal("CSV に 'student_id' または '学生番号' 列が見つかりません。")
    df[sid_col] = df[sid_col].str.lstrip("0")
    before = len(df)
    df = df.drop_duplicates(subset=sid_col, keep="last")
    after = len(df)
    print(f"✅ Deduplicated: {before - after} duplicates removed, {after} unique students")

    # --- 4) パスワード列の検証 ---
    if "password" in df.columns:
        pwd_col = "password"
    elif "パスワード" in df.columns:
        pwd_col = "パスワード"
    else:
        fatal("CSV に 'password' または 'パスワード' 列が見つかりません。")
    
    # --- 5) ハッシュ生成 & 行構築 ---
    rows = []
    for idx, row in df.iterrows():
        sid = row[sid_col]
        pwd = row.get(pwd_col, "")
        if pd.isna(pwd) or pwd.strip() == "":
            # パスワード未入力はスキップ
            continue
        hash_hex = hashlib.sha256((pwd + pepper).encode("utf-8")).hexdigest()
        role = "admin" if sid == "22" else "student"
        rows.append({"student_id": sid, "password_hash": hash_hex, "role": role})
    if not rows:
        fatal("有効なパスワード付きレコードが CSV に見つかりませんでした。")
    print(f"✅ Prepared {len(rows)} auth entries")

    # --- 6) CSV 書き出し ---
    auth_df = pd.DataFrame(rows, columns=["student_id", "password_hash", "role"])
    try:
        auth_df.to_csv("auth.csv", index=False)
    except Exception as e:
        fatal(f"auth.csv の書き出しに失敗しました: {e}")
    print("✅ auth.csv を生成しました")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
