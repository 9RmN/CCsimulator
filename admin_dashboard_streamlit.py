import streamlit as st
import pandas as pd
import subprocess
import hashlib

# --- 認証ステートの初期化 ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'admin_id' not in st.session_state:
    st.session_state['admin_id'] = None

# --- ログアウト処理 ---
if st.session_state['authenticated']:
    if st.sidebar.button("ログアウト"):
        st.session_state['authenticated'] = False
        st.session_state['admin_id'] = None
        # ページを更新してください

# --- 認証フォーム表示 ---
if not st.session_state['authenticated']:
    st.title("🔒 管理者ログイン")
    sid_input = st.text_input("管理者ID", "")
    pwd_input = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        try:
            auth_df = pd.read_csv(
                "auth.csv",
                dtype={
                    'student_id': str,
                    'password_hash': str,
                    'role': str
                }
            )
        except FileNotFoundError:
            st.error("auth.csv が見つかりません。管理者用認証データを配置してください。")
            st.stop()
        pepper = st.secrets["pepper"]
        hashed = hashlib.sha256((pwd_input + pepper).encode()).hexdigest()
        row = auth_df[
            (auth_df['student_id'] == sid_input) &
            (auth_df['password_hash'] == hashed) &
            (auth_df['role'] == 'admin')
        ]
        if not row.empty:
            st.session_state['authenticated'] = True
            st.session_state['admin_id'] = sid_input
            st.success(f"認証成功：管理者ID {sid_input}")
            # ページを更新してください
        else:
            st.error("認証失敗：IDまたはパスワードが違うか、管理者権限がありません。")
    st.stop()

# --- 管理者認証後コンテンツ ---
st.sidebar.write(f"👤 管理者: {st.session_state['admin_id']}")

# 自動リフレッシュ: 5分ごとにブラウザが自動更新
st.markdown(
    '<meta http-equiv="refresh" content="300">',
    unsafe_allow_html=True,
)

@st.cache_data(ttl=300)
def load_data():
    # 全パイプラインを実行（最新データを生成）
    subprocess.run(['python', 'update_all.py'], check=True)

    # responses.csv 読み込み + 正規化
    responses_df = pd.read_csv("responses.csv", dtype=str)
    responses_df['student_id'] = responses_df['student_id'].str.lstrip('0')
    responses_df = responses_df.drop_duplicates(subset='student_id', keep='last')

    # 抽選順位情報読み込み
    lottery_df = pd.read_csv(
        "lottery_order.csv",
        dtype={'student_id': str, 'lottery_order': int}
    )
    # 必須の分析CSV読み込み
    def load_optional(file):
        try:
            return pd.read_csv(file)
        except FileNotFoundError:
            return None
    assign_matrix = load_optional("assignment_matrix.csv")
    dept_summary  = load_optional("department_summary.csv")

    return responses_df, lottery_df, assign_matrix, dept_summary

# データロード
responses_df, lottery_df, assign_matrix, dept_summary = load_data()

st.title("管理者ダッシュボード")

# 手動更新ボタン：キャッシュクリア & 再実行
def refresh():
    st.cache_data.clear()
    # ページを更新してください

st.button("🌀 最新データを取得", on_click=refresh)

# 回答率表示
answered_ids = set(responses_df['student_id'])
all_ids = [str(i) for i in range(1, 111)]
answered_count = len(answered_ids & set(all_ids))
total_count = len(all_ids)
st.markdown(f"**回答済み：{answered_count} / {total_count} 人**")

# 学生番号一覧（未回答は赤背景）
df_ids = pd.DataFrame({'student_id': all_ids})
df_ids['answered'] = df_ids['student_id'].isin(answered_ids)
def highlight_unanswered(val):
    return 'background-color: #f8d7da' if not val else ''
st.subheader("学生番号一覧（未回答は赤背景）")
# 'answered' 列で背景色を付け、非表示にする
styled = (
    df_ids.style
    .applymap(highlight_unanswered, subset=['answered'])
    .hide(axis='columns', subset=['answered'])
)
st.dataframe(styled, use_container_width=True)

# 配属マトリクス表示
st.subheader("配属マトリクス（学生×Term）")
if assign_matrix is not None:
    st.dataframe(assign_matrix, use_container_width=True)
else:
    st.warning("assignment_matrix.csv が見つかりません。生成後、再デプロイしてください。")

# 部門サマリ表示
st.subheader("部門サマリ（希望者数・定員・配属数・中央値）")
if dept_summary is not None:
    st.dataframe(dept_summary, use_container_width=True)
else:
    st.warning("department_summary.csv が見つかりません。生成後、再デプロイしてください。")

# 🧪 仮希望入力シミュレーション（管理者専用）
st.header("🧪 仮希望入力シミュレーション（非公開ツール）")
prob_df = pd.read_csv("probability_montecarlo_combined.csv", dtype={'student_id': str})

# department_capacity.csv からマスターリスト生成
cap_df = pd.read_csv("department_capacity.csv")
hd = cap_df["hospital_department"].str.split("-", n=1, expand=True)
hospital_list   = sorted(hd[0].unique())
department_list = sorted(hd[1].unique())

student_id = st.text_input("仮想 Student ID", value="22", disabled=True)
lottery_number = st.number_input("仮想 抽選順位", min_value=1, max_value=9999, value=101, disabled=True)

st.subheader("🎯 第1〜第10希望を入力（病院＋診療科）")
input_hopes = []
for i in range(1, 11):
    col1, col2 = st.columns(2)
    with col1:
        hospital = st.selectbox(f"第{i}希望：病院", [""] + hospital_list, key=f"hospital_{i}")
    with col2:
        department = st.selectbox(f"第{i}希望：診療科", [""] + department_list, key=f"dept_{i}")
    if hospital and department:
        input_hopes.append(f"{hospital}-{department}")

if st.button("🧮 シミュレーション実行"):
    for idx, dept in enumerate(input_hopes, start=1):
        col_name_prob = f"hope_{idx}_確率"
        if student_id and col_name_prob in prob_df.columns:
            row = prob_df[prob_df['student_id'] == student_id]
            prob = row.iloc[0][col_name_prob] if not row.empty else None
            st.write(f"第{idx}希望: {dept} → 通過確率: {prob if prob is not None else '不明'}")
        else:
            st.write(f"第{idx}希望: {dept} → 通過確率データ未整備")

# 抽選順位中央値表示
st.header("🏁 診療科ごとの通過順位中央値（通過ライン推定）")
try:
    assignment_df = pd.read_csv("initial_assignment_result.csv", dtype={'student_id': str, 'assigned_department': str, 'term': str})
    lottery_df    = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    merged_df     = assignment_df.merge(lottery_df, on="student_id")
    result = (
        merged_df.groupby(["assigned_department", "term"])['lottery_order']
        .median()
        .reset_index()
        .rename(columns={'lottery_order': '抽選順位中央値'})
        .sort_values('抽選順位中央値')
    )
    st.dataframe(result, use_container_width=True)
    st.markdown("⬇️ 抽選順位中央値が小さいほど人気が高い診療科を示します")
except FileNotFoundError:
    st.warning("initial_assignment_result.csv が見つかりません。生成後、再デプロイしてください。")
