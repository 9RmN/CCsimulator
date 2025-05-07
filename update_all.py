import os
import pandas as pd
import subprocess
from google.auth import default
from googleapiclient.discovery import build

# --- 環境変数チェック ---
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise RuntimeError("環境変数 SPREADSHEET_ID が設定されていません。")
# シート範囲（必要に応じてシート名を調整）
RANGE_NAME = os.environ.get("RANGE_NAME", "'フォームの回答'!A1:AZ1000")

# --- Application Default Credentials で認証 ---
creds, _ = default(scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
service = build("sheets", "v4", credentials=creds)

# Step 1: Googleフォーム回答を取得
print("📥 Googleフォーム回答を取得中...")
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=RANGE_NAME
).execute()
values = result.get("values", [])
if not values:
    print("❌ データが取得できませんでした")
    exit(1)

df = pd.DataFrame(values[1:], columns=values[0])
df.to_csv("form_responses_final.csv", index=False)
print("✅ form_responses_final.csv を保存しました")

# Step 2: responses.csv に変換＋重複排除
print("🔄 responses.csv に変換中...")
try:
    df2 = pd.read_csv("form_responses_final.csv", dtype=str)
    output = {
        "student_id": df2.iloc[:, 1].str.lstrip("0"),
        "password":   df2.iloc[:, 2]
    }
    for i in range(1, 21):
        hcol = i * 2 + 1
        dcol = i * 2 + 2
        try:
            hosp = df2.iloc[:, hcol].fillna("")
            dept = df2.iloc[:, dcol].fillna("")
            combined = (hosp + "-" + dept).str.strip().replace("", pd.NA)
            output[f"hope_{i}"] = combined
        except Exception:
            output[f"hope_{i}"] = pd.NA
    responses = pd.DataFrame(output)
    before = len(responses)
    responses = responses.drop_duplicates(subset="student_id", keep="last")
    deleted = before - len(responses)
    print(f"✅ 重複排除: {deleted} 件削除, 残り {len(responses)} 件")
    responses.to_csv("responses.csv", index=False)
    print("✅ responses.csv を生成しました")
except Exception as e:
    print("❌ responses.csv への変換に失敗:", e)
    exit(1)

# Step 2.5: auth.csv を再生成
print("🔐 auth.csv を再生成中…")
subprocess.run(["python", "-u", "generate_auth.py"], check=True)
print("✅ auth.csv を生成しました")

# --- その他スクリプト実行 ---
scripts = [
    "initial_assignment.py",
    "simulate_with_unanswered.py",
    "generate_probability.py",
    "generate_popular_rank.py",
    "analyze_assignment.py",
    "analyze_department.py"
]
for script in scripts:
    print(f"⚙️ {script} を実行中...")
    subprocess.run(["python", script], check=True)

print("\n✅ 全パイプライン実行完了！")
