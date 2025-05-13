import os
import streamlit as st
import pandas as pd
import hashlib
import altair as alt
import importlib
import simulate_each_as_first  # 通過確率シミュレーション（仮に第1希望とした場合）

# --- 自動リフレッシュ ---
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

# --- セッションステート初期化 ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = ''

# --- Pepper の取得 ---
try:
    PEPPER = st.secrets['auth']['pepper']
except Exception:
    PEPPER = os.environ.get('PEPPER')
    if not PEPPER:
        st.error("⚠️ Pepper が設定されていません。認証に失敗します。")
        st.stop()

# --- データロード ---
@st.cache_data(ttl=60)
def load_data():
    prob_df      = pd.read_csv("probability_montecarlo_combined.csv", dtype={'student_id': str})
    auth_df      = pd.read_csv("auth.csv", dtype={'student_id': str, 'password_hash': str, 'role': str})
    rank_df      = pd.read_csv("popular_departments_rank_combined.csv")
    terms_df     = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    responses_df = pd.read_csv("responses.csv", dtype={'student_id': str})

    for df in [responses_df, prob_df, terms_df, auth_df]:
        df['student_id'] = df['student_id'].str.lstrip('0')

    responses_df.set_index('student_id', inplace=True)
    prob_df.set_index('student_id', inplace=True)
    terms_df.set_index('student_id', inplace=True)
    auth_df.set_index('student_id', inplace=True)

    return prob_df, auth_df, rank_df, terms_df, responses_df

# --- データ読み込み ---
prob_df, auth_df, rank_df, terms_df, responses_df = load_data()

# --- 認証 ---
def verify_user(sid, pwd):
    sid = sid.lstrip('0')
    if not sid.isdigit():
        return False
    if sid not in auth_df.index:
        return False
    row = auth_df.loc[sid]
    if row['role'] not in ['student', 'admin']:
        return False
    hashed = hashlib.sha256((pwd + PEPPER).encode()).hexdigest()
    return hashed == row['password_hash']

if not st.session_state['authenticated']:
    st.title("🔐 ログイン")
    sid = st.text_input("学生番号", value="", key="login_uid")
    pwd = st.text_input("パスワード", type="password", key="login_pwd")
    if st.button("ログイン"):
        with st.spinner("ログイン中... シミュレーションの準備に少し時間がかかることがあります"):
            if verify_user(sid, pwd):
                st.session_state['authenticated'] = True
                st.session_state['user_id'] = sid.lstrip('0')
                st.success(f"認証成功: 学生番号={sid.lstrip('0')}")
            else:
                st.error("学生番号またはパスワードが間違っています")
    st.stop()

# --- 認証後画面 ---
sid = st.session_state['user_id']
st.title(f"🎓 選択科アンケート (学生番号={sid})")

# --- 回答状況表示 ---
all_count      = len(terms_df)
answered_count = responses_df.shape[0]
ratio          = answered_count / all_count * 100
st.markdown(f"🧾 **回答者：{answered_count} / {all_count}人**（{ratio:.1f}%）")
if ratio < 70:
    st.warning("⚠️ 回答者が少ないため、結果がまだ不安定です。")

# --- 通過確率シミュレーション実行 ---
st.subheader("🌀 通過確率（仮に第1希望とした場合）")
if st.button("♻️ 再シミュレーションを実行"):
    simulate_each_as_first = importlib.reload(simulate_each_as_first)
    st.success("再シミュレーションを実行しました。")

try:
    with st.spinner("シミュレーションを実行中です..."):
        flat_df = simulate_each_as_first.simulate_each_as_first(sid)
except Exception as e:
    st.error(f"シミュレーションエラー: {e}")
    st.stop()

# --- 希望一覧＋通過確率比較 ---
st.subheader("🎯 希望科通過確率一覧（順位あり / 仮に第1希望とした場合）")
# ... (略) ...

# --- 人気診療科表示 ---
st.subheader("🔥 人気診療科トップ15 (抽選順位中央値)")
median_col = rank_df.columns[1]
rank_df[median_col] = pd.to_numeric(rank_df[median_col], errors='coerce')
top15 = rank_df.groupby(rank_df.columns[0])[median_col].median().nsmallest(15)
chart_df = top15.reset_index().rename(
    columns={rank_df.columns[0]: '診療科', median_col: '抽選順位中央値'}
)
# 昇順ソート（有利順）
chart = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        x=alt.X('抽選順位中央値:Q'),
        y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending'))
    )
    .properties(height=400)
)
text = (
    alt.Chart(chart_df)
    .mark_text(align='left', dx=3, baseline='middle')
    .encode(
        x=alt.X('抽選順位中央値:Q'),
        y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending')),
        text=alt.Text('抽選順位中央値:Q')
    )
)
st.altair_chart(chart + text, use_container_width=True)

# --- 昨年上限に達した科の最大通過順位 ---
st.subheader("🔖 昨年：上限に達した科の最大通過順位（バーグラフ）")

hist_df = pd.read_csv("2024配属結果.csv", dtype={'student_id': str, 'lottery_order': int})
cap_df  = pd.read_csv("department_capacity.csv")
term_cols = [c for c in hist_df.columns if c.startswith("term_")]
records = []
for _, r in hist_df.iterrows():
    rank = r["lottery_order"]
    for term in term_cols:
        dept = r[term]
        if pd.notna(dept) and dept not in ("","-"):
            records.append({"department": dept, "term": term, "lottery_order": rank})
# longフォーマット展開
