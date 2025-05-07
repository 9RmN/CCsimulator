import os
import json
import subprocess
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 環境変数から取得
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
RANGE_NAME = os.environ.get("RANGE_NAME", "フォームの回答!A1:AZ1000")
GOOGLE_CREDS  = os.environ["GOOGLE_CREDENTIALS"]  # JSON 文字列

# Step 1: Googleフォーム回答を取得
print("📥 Googleフォーム回答を取得中...")
info = json.loads(GOOGLE_CREDS)
creds = service_account.Credentials.from_service_account_info(
    info,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
service = build('sheets', 'v4', credentials=creds)
sheet   = service.spreadsheets()
result  = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
values  = result.get('values', [])

if not values:
    print("❌ データが取得できませんでした")
    exit(1)

df = pd.DataFrame(values[1:], columns=values[0])
df.to_csv("form_responses_final.csv", index=False)
print("✅ form_responses_final.csv を保存しました")

# Step 2: responses.csv に変換＋重複排除
print("🔄 responses.csv に変換中...")
try:
    df = pd.read_csv("form_responses_final.csv")
    output = {
        "student_id": df.iloc[:, 1],
        "password":   df.iloc[:, 2],
    }
    # 希望列を最大20まで
    for i in range(1, 21):
        hcol = i*2 + 1
        dcol = i*2 + 2
        try:
            hosp = df.iloc[:, hcol].fillna("")
            dept = df.iloc[:, dcol].fillna("")
            combined = (hosp + "-" + dept).str.strip().replace("", pd.NA)
            output[f"hope_{i}"] = combined
        except:
            output[f"hope_{i}"] = pd.NA

    responses = pd.DataFrame(output)
    responses['student_id'] = responses['student_id'].astype(str).str.lstrip('0')
    before = len(responses)
    responses = responses.drop_duplicates(subset='student_id', keep='last')
    after  = len(responses)
    print(f"✅ 重複排除: {before-after} 件削除, 残り {after} 件")
    responses.to_csv("responses.csv", index=False)
    print("✅ responses.csv を生成しました\n")

except Exception as e:
    print("❌ responses.csv への変換に失敗:", e)
    exit(1)

# Step 2.5: auth.csv の作成
print("🔐 auth.csv を再生成中…")
subprocess.run(["python", "-u", "generate_auth.py"], check=True)
print("✅ auth.csv を生成しました")

# 以下、既存のステップをそのまま呼び出し
print("⚙️ initial_assignment.py を実行中...")
subprocess.run(['python', 'initial_assignment.py'], check=True)

print("⚙️ simulate_with_unanswered.py を実行中...")
subprocess.run(['python', 'simulate_with_unanswered.py'], check=True)

print("⚙️ generate_probability.py を実行中...")
subprocess.run(['python', 'generate_probability.py'], check=True)

print("⚙️ generate_popular_rank.py を実行中...")
subprocess.run(['python', 'generate_popular_rank.py'], check=True)

print("⚙️ analyze_assignment.py を実行中...")
subprocess.run(['python', 'analyze_assignment.py'], check=True)

print("⚙️ analyze_department.py を実行中...")
subprocess.run(['python', 'analyze_department.py'], check=True)

print("\n✅ 全パイプライン実行完了！")
