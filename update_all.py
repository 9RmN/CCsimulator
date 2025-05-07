import os
import subprocess
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 環境変数  ---
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
RANGE_NAME    = 'フォームの回答 1!A1:AZ1000'
SERVICE_ACCOUNT_FILE = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# Step 1: Googleフォーム回答を取得
print("📥 Googleフォーム回答を取得中...")
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
values = result.get('values', [])

if not values:
    print("❌ データが取得できませんでした")
    exit(1)

df = pd.DataFrame(values[1:], columns=values[0])
df.to_csv("form_responses_final.csv", index=False)
print("✅ form_responses_final.csv を保存しました")

# Step 2: responses.csv に変換＋重複排除
print("🔄 responses.csv に変換中...")
try:
    df = pd.read_csv("form_responses_final.csv", dtype=str)

    output = {
        "student_id": df.iloc[:, 1],
        "password": df.iloc[:, 2],
    }

    for i in range(1, 21):
        hospital_col   = i * 2 + 1
        department_col = i * 2 + 2
        try:
            hospital   = df.iloc[:, hospital_col].fillna("")
            department = df.iloc[:, department_col].fillna("")
            combined   = hospital + "-" + department
            output[f"hope_{i}"] = combined.str.strip().replace("", pd.NA)
        except Exception:
            output[f"hope_{i}"] = pd.NA

    responses = pd.DataFrame(output)
    responses['student_id'] = responses['student_id'].str.lstrip('0')
    before = len(responses)
    responses = responses.drop_duplicates(subset='student_id', keep='last')
    after = len(responses)
    print(f"✅ 重複排除: {before - after} 件削除, 残り {after} 件")

    responses.to_csv("responses.csv", index=False)
    print("✅ responses.csv を生成しました\n")

except Exception as e:
    print("❌ responses.csv への変換に失敗しました:", e)
    exit(1)

# Step 3: auth.csv の再生成
print("🔐 auth.csv を再生成中…")
subprocess.run(["python", "generate_auth.py"], check=True)
print("✅ auth.csv を生成しました")

# Step 4: 初期配属
print("⚙️ initial_assignment.py を実行中...")
subprocess.run(['python', 'initial_assignment.py'], check=True)

# Step 5: 未回答者を含めた配属シミュレーション
print("⚙️ simulate_with_unanswered.py を実行中...")
subprocess.run(['python', 'simulate_with_unanswered.py'], check=True)

# Step 6: Monte Carlo 確率生成
print("⚙️ generate_probability.py を実行中...")
subprocess.run(['python', 'generate_probability.py'], check=True)

# Step 7: 人気科ランキング生成
print("⚙️ generate_popular_rank.py を実行中...")
subprocess.run(['python', 'generate_popular_rank.py'], check=True)

# Step 8: 結果分析
print("⚙️ analyze_assignment.py を実行中...")
subprocess.run(['python', 'analyze_assignment.py'], check=True)
print("⚙️ analyze_department.py を実行中...")
subprocess.run(['python', 'analyze_department.py'], check=True)

print("\n✅ 全パイプライン実行完了！")
