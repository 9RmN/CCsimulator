import subprocess
import pandas as pd
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 認証情報の設定
# 環境変数 GOOGLE_APPLICATION_CREDENTIALS を参照、未設定時はデフォルトの service_account.json
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
RANGE_NAME = 'フォームの回答 1!A1:AZ1000'

# Step 1: Googleフォーム回答を取得
print("📥 Googleフォーム回答を取得中...")
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
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
    df = pd.read_csv("form_responses_final.csv")

    output = {
        "student_id": df.iloc[:, 1],
        "password": df.iloc[:, 2],
    }

    for i in range(1, 21):
        hospital_col = i * 2 + 1
        department_col = i * 2 + 2
        try:
            hospital = df.iloc[:, hospital_col]
            department = df.iloc[:, department_col]
            combined = hospital.fillna("") + "-" + department.fillna("")
            output[f"hope_{i}"] = combined.str.strip().replace("", pd.NA)
        except Exception:
            output[f"hope_{i}"] = pd.NA

    responses = pd.DataFrame(output)

    # 学生番号 normalization: 先頭の '0' を除去
    responses['student_id'] = responses['student_id'].astype(str).str.lstrip('0')

    # 重複削除: 新しいものを残す
    before = len(responses)
    responses = responses.drop_duplicates(subset='student_id', keep='last')
    after = len(responses)
    print(f"✅ 重複排除: {before - after} 件削除, 残り {after} 件")

    responses.to_csv("responses.csv", index=False)
    print("✅ responses.csv を生成しました\n")

except Exception as e:
    print("❌ responses.csv への変換に失敗しました:", e)
    exit(1)

print("🔐 auth.csv を再生成中…")
subprocess.run(["python", "generate_auth.py"], check=True)
print("✅ auth.csv を生成しました")

# Debug: hope_1 のユニーク値確認
print("Debug: hope_1 のユニーク値:", sorted(responses['hope_1'].dropna().unique()))

# Step 3: 初期配属
print("⚙️ initial_assignment.py を実行中...")
subprocess.run(['python', 'initial_assignment.py'], check=True)

# Step 4: 未回答者を含めた配属シミュレーション
print("⚙️ simulate_with_unanswered.py を実行中...")
subprocess.run(['python', 'simulate_with_unanswered.py'], check=True)

# Step 5: Monte Carlo 確率生成
print("⚙️ generate_probability.py を実行中...")
subprocess.run(['python', 'generate_probability.py'], check=True)

# Step 6: 人気科ランキング生成
print("⚙️ generate_popular_rank.py を実行中...")
subprocess.run(['python', 'generate_popular_rank.py'], check=True)

# Step 7: 結果分析
print("⚙️ analyze_assignment.py を実行中...")
subprocess.run(['python', 'analyze_assignment.py'], check=True)
print("⚙️ analyze_department.py を実行中...")
subprocess.run(['python', 'analyze_department.py'], check=True)

print("\n✅ 全パイプライン実行完了！")
