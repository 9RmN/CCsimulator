import os
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
import altair as alt
import importlib
import simulate_each_as_first  # 通過確率シミュレーション

# --- 自動リフレッシュ ---
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

# --- セッションステート初期化 ---
for key in ['authenticated','user_id','flat_df']:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state['authenticated'] is None:
    st.session_state['authenticated'] = False
if st.session_state['user_id'] is None:
    st.session_state['user_id'] = ''

# --- Pepper の取得 ---
try:
    PEPPER = st.secrets['auth']['pepper']
except:
    PEPPER = os.environ.get('PEPPER')
    if not PEPPER:
        st.error("⚠️ Pepper が設定されていません。認証に失敗します。")
        st.stop()

# --- データロード ---
@st.cache_data(ttl=60)
def load_data():
    prob_df      = pd.read_csv("probability_montecarlo_combined.csv", dtype={'student_id':str})
    auth_df      = pd.read_csv("auth.csv", dtype={'student_id':str,'password_hash':str,'role':str})
    rank_df      = pd.read_csv("popular_departments_rank_combined.csv")
    terms_df     = pd.read_csv("student_terms.csv", dtype={'student_id':str})
    responses_df = pd.read_csv("responses.csv", dtype={'student_id':str})
    for df in [responses_df,prob_df,terms_df,auth_df]:
        df['student_id'] = df['student_id'].str.lstrip('0')
    responses_df.set_index('student_id',inplace=True)
    prob_df.set_index('student_id',inplace=True)
    terms_df.set_index('student_id',inplace=True)
    auth_df.set_index('student_id',inplace=True)
    return prob_df, auth_df, rank_df, terms_df, responses_df

prob_df, auth_df, rank_df, terms_df, responses_df = load_data()

# --- 認証 ---
def verify_user(sid, pwd):
    sid = sid.lstrip('0')
    if not sid.isdigit() or sid not in auth_df.index:
        return False
    row = auth_df.loc[sid]
    if row['role'] not in ['student','admin']:
        return False
    return hashlib.sha256((pwd+PEPPER).encode()).hexdigest() == row['password_hash']

if not st.session_state['authenticated']:
    sid = st.text_input("学生番号", key="login_uid")
    pwd = st.text_input("パスワード", type="password", key="login_pwd")
    if st.button("ログイン"):
        if verify_user(sid,pwd):
            st.session_state['authenticated']=True
            st.session_state['user_id']=sid.lstrip('0')
            st.experimental_rerun()
        else:
            st.error("認証に失敗しました。")
    st.stop()

# --- 認証後画面 ---
sid = st.session_state['user_id']
st.title(f"🎓 選択科アンケート (学生番号={sid})")

# --- 回答状況表示 ---
all_count = len(terms_df)
answered_count = responses_df.shape[0]
ratio = answered_count/all_count*100
st.markdown(f"🧾 **回答者：{answered_count}/{all_count}人** ({ratio:.1f}%)")
if ratio<70:
    st.warning("⚠️ 回答者が少ないため結果が不安定です。")

# --- 通過確率シミュレーション ---
st.subheader("🌀 通過確率（仮に第1希望とした場合）")
if st.button("♻️ シミュレーション実行"):
    simulate_each_as_first = importlib.reload(simulate_each_as_first)
    st.session_state['flat_df'] = simulate_each_as_first.simulate_each_as_first(sid)
if st.session_state['flat_df'] is None:
    with st.spinner("初回シミュレーション実行中..."):
        st.session_state['flat_df'] = simulate_each_as_first.simulate_each_as_first(sid)
flat_df = st.session_state['flat_df']

# --- 希望科通過確率一覧 ---
st.subheader("🎯 希望科通過確率一覧（順位あり/仮に第1希望）")
display=[]
for i in range(1,21):
    hope = responses_df.loc[sid].get(f"hope_{i}")
    if not hope: continue
    pr = prob_df.loc[sid].get(f"hope_{i}_確率")
    col="通過確率（仮に第1希望とした場合）"
    if col not in flat_df.columns: col="通過確率"
    pf = flat_df.loc[flat_df["希望科"]==hope, col].values[0] if hope in flat_df["希望科"].values else ""
    display.append({'希望':f"{i}: {hope}",'順位あり':f"{int(pr)}%" if pd.notna(pr) else "",'仮1':pf})
st.dataframe(pd.DataFrame(display), use_container_width=True)

# --- 人気診療科表示 ---
st.subheader("🔥 人気診療科トップ15 (抽選順位中央値)")
median_col = rank_df.columns[1]
rank_df[median_col] = pd.to_numeric(rank_df[median_col], errors='coerce')
top15 = rank_df.groupby(rank_df.columns[0])[median_col].median().nsmallest(15)
chart_df = top15.reset_index().rename(columns={rank_df.columns[0]: '診療科', median_col: '抽選順位中央値'})

# バーを順位小さい順にソートし、右側に数値ラベルを表示
chart = alt.Chart(chart_df).mark_bar().encode(
    x=alt.X('抽選順位中央値:Q', title='抽選順位中央値'),
    y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending'), title=None)
).properties(width=700, height= max(300, len(chart_df)*25))

text = chart.mark_text(
    align='left',
    baseline='middle',
    dx=3
).encode(
    text=alt.Text('抽選順位中央値:Q')
)

# 軸ラベルを回転して表示領域を確保し、表示名を完全に出す
chart = chart.configure_axis(
    labelFontSize=12,
    titleFontSize=14,
    labelAngle=0,
    labelAlign='right'
)

st.altair_chart(chart + text, use_container_width=True)

# --- 昨年上限に達した科の最大通過順位 ---
st.subheader("🔖 昨年：配属上限に達した科の最大通過順位（バーグラフ）")
# (以降略)
