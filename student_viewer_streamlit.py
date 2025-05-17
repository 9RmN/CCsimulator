import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
import altair as alt
import re

# Ensure current directory is in module path
sys.path.insert(0, os.getcwd())

# --- 自動リフレッシュ ---
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

# --- セッションステート初期化 ---
for key in ['authenticated','user_id']:
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
    terms_df     = pd.read_csv(
        "student_terms.csv",
        dtype={'student_id':str,'term_1':int,'term_2':int,'term_3':int,'term_4':int}
    )
    responses_df = pd.read_csv("responses.csv", dtype={'student_id':str})
    first_choice_df = pd.read_csv("first_choice_probabilities.csv", dtype={'student_id':str})

    # student_id の前ゼロ除去
    for df in [responses_df, prob_df, terms_df, auth_df, first_choice_df]:
        df['student_id'] = df['student_id'].str.lstrip('0')

    # インデックス設定
    responses_df.set_index('student_id', inplace=True)
    prob_df.set_index('student_id', inplace=True)
    terms_df.set_index('student_id', inplace=True)
    auth_df.set_index('student_id', inplace=True)
    first_choice_df.set_index('student_id', inplace=True)

    return prob_df, auth_df, rank_df, terms_df, responses_df, first_choice_df

prob_df, auth_df, rank_df, terms_df, responses_df, first_choice_df = load_data()

# --- 追加データロード ---
# 初期配属結果
assignment_df = pd.read_csv(
    "initial_assignment_result.csv",
    dtype={'student_id':str,'term':int,'assigned_department':str,'matched_priority':float}
)
assignment_df['student_id'] = assignment_df['student_id'].str.lstrip('0')

# 抽選順位
lottery_df = pd.read_csv(
    "lottery_order.csv",
    dtype={'student_id':str,'lottery_order':int}
)
lottery_df['student_id'] = lottery_df['student_id'].str.lstrip('0')
lottery_df.set_index('student_id', inplace=True)

# department_capacity
capacity_df = pd.read_csv(
    "department_capacity.csv",
    dtype=str
)
# 数値型に変換 (term_ 列のみ)
for col in capacity_df.columns:
    if col.startswith('term_'):
        # 数字部分を抽出し、欠損は0で埋めてから int 型に
        extracted = capacity_df[col].str.extract(r"(\d+)")
        capacity_df[col] = extracted.iloc[:, 0].fillna('0').astype(int)
# hospital_department 列はそのまま文字列として扱う
capacity_df['hospital_department'] = capacity_df['hospital_department'].astype(str)

# --- 認証関数 ---
def verify_user(sid, pwd):
    sid = sid.lstrip('0')
    if not sid.isdigit() or sid not in auth_df.index:
        return False
    row = auth_df.loc[sid]
    if row['role'] not in ['student','admin']:
        return False
    return hashlib.sha256((pwd + PEPPER).encode()).hexdigest() == row['password_hash']

# --- ログイン画面 ---
if not st.session_state['authenticated']:
    st.title("🔐 ログイン")
    sid_input = st.text_input("学生番号", key="login_uid")
    pwd_input = st.text_input("パスワード", type="password", key="login_pwd")
    if st.button("ログイン"):
        if verify_user(sid_input, pwd_input):
            st.session_state['authenticated'] = True
            st.session_state['user_id'] = sid_input.lstrip('0')
        else:
            st.error("認証に失敗しました。")
    st.stop()

# --- 認証後メイン画面 ---
sid = st.session_state['user_id']
st.title(f"🎓 選択科アンケート (学生番号={sid})")

# 回答率表示
all_count = len(terms_df)
answered_count = len(responses_df)
ratio = answered_count / all_count * 100
st.markdown(f"🧾 **回答者：{answered_count}/{all_count} 人**（{ratio:.1f}%）")
if ratio < 70:
    st.warning("⚠️ 回答者が少ないため結果が不安定です。回答を促してください。")

# --- 機能1: 初期配属結果 ---
st.subheader("🗒️ 初期配属結果")
my_assign = assignment_df[assignment_df['student_id'] == sid]
if not my_assign.empty:
    st.dataframe(
        my_assign.sort_values('term').set_index('term')[['assigned_department','matched_priority']],
        use_container_width=True
    )
else:
    st.info("初期配属結果が見つかりません。")

# --- 機能2: 第1希望通過確率 ---
st.subheader("📈 第1希望通過確率")
if sid in first_choice_df.index:
    my_first = first_choice_df.loc[[sid]]
    st.dataframe(
        my_first[['希望科','通過確率']],
        use_container_width=True
    )
else:
    st.info("第1希望通過確率のデータがありません。")

# --- 機能3: 第1～5希望人数表示（自分より抽選順位が高い学生のみ） ---
st.subheader("📊 第1～5希望人数 (科ごと・Term1～Term11) - 自分より抽選順位が高い学生のみ")
my_order = lottery_df.loc[sid, 'lottery_order']
higher = lottery_df[lottery_df['lottery_order'] < my_order].index.tolist()

counts = {}
for uid in higher:
    if uid not in responses_df.index:
        continue
    default_terms = terms_df.loc[uid, ['term_1','term_2','term_3','term_4']].tolist()
    for i in range(1, 6):
        dept = responses_df.loc[uid].get(f'hope_{i}')
        if pd.isna(dept) or not dept or dept == '-':
            continue
        raw = responses_df.loc[uid].get(f'hope_{i}_terms', '')
        nums = [int(n) for n in re.findall(r"\d+", str(raw))]
        term_list = [t for t in nums if t in default_terms]
        use_terms = term_list if term_list else default_terms
        for t in use_terms:
            counts[(dept, t)] = counts.get((dept, t), 0) + 1
rows = [{'診療科': dept, 'Term': term, '人数': cnt} for (dept, term), cnt in counts.items()]
cnt_df = pd.DataFrame(rows)
if cnt_df.empty:
    st.info("該当するデータがありません。")
else:
    pivot = cnt_df.pivot(index='診療科', columns='Term', values='人数').fillna(0).astype(int)
    st.dataframe(pivot, use_container_width=True)

# --- 枠埋まり科（科単位集計）と最大抽選順位 ---
st.subheader("🏥 枠埋まり科（科単位集計）と最大抽選順位")

THRESHOLD_RATE = 1.0
# capacity_df は上部で読み込み済み
# valid 割当
valid = assignment_df[assignment_df['assigned_department'] != '未配属']
assigned_counts = (
    valid
    .groupby(['assigned_department', 'term'])
    .size()
    .reset_index(name='assigned_count')
    .rename(columns={'assigned_department': 'hospital_department'})
)
merged = assigned_counts.merge(
    capacity_df.melt(id_vars=['hospital_department'], var_name='term_label', value_name='capacity')
    .assign(
        term=lambda df: df['term_label'].str.extract(r'_(\d+)').astype(int),
        capacity=lambda df: df['capacity'].astype(int)
    )
    .drop(columns='term_label'),
    on=['hospital_department', 'term']
)
merged['fill_rate'] = merged['assigned_count'] / merged['capacity']
full = merged[merged['fill_rate'] >= THRESHOLD_RATE]

with_lottery = valid.merge(lottery_df.reset_index(), on='student_id')
# 枠埋まり対象だけ抽出
key_set = set(full[['hospital_department', 'term']].itertuples(index=False, name=None))
filled = with_lottery[
    with_lottery.apply(lambda r: (r['assigned_department'], r['term']) in key_set, axis=1)
]

dept_summary = (
    filled
    .groupby('assigned_department')
    .agg(
        配属人数合計=('student_id', 'nunique'),
        最大抽選順位=('lottery_order', 'max')
    )
    .reset_index()
    .rename(columns={'assigned_department': '科名'})
    .sort_values('配属人数合計', ascending=False)
    .head(15)
)
st.dataframe(dept_summary, use_container_width=True)

# --- 昨年：一定割合以上配属された科の最大通過順位 ---
st.subheader("🔖 昨年：一定割合以上配属された科の最大通過順位")
# データ読み込み
hist_df = pd.read_csv("2024配属結果.csv", dtype={'student_id':str, 'lottery_order':int})
cap_df  = pd.read_csv("department_capacity2024.csv")
# 長い形式に変換
records = []
term_cols = [c for c in hist_df.columns if c.startswith('term_')]
for _, r in hist_df.iterrows():
    rank = r['lottery_order']
    for term in term_cols:
        dept = r[term]
        if pd.notna(dept) and dept not in ('','-'):
            records.append({'department':dept,'lottery_order':rank})
df_long2 = pd.DataFrame(records)
# 部門ごと配属数
assign_dept = df_long2.groupby('department',as_index=False).size().rename(columns={'size':'assigned_count'})
# capacity合計
cap_dept = (cap_df.melt(id_vars=['hospital_department'], value_vars=[c for c in cap_df.columns if c.startswith('term_')], var_name='term', value_name='capacity')
                .groupby('hospital_department',as_index=False).agg({'capacity':'sum'}).rename(columns={'hospital_department':'department'}))
# 配属率閾値
threshold = st.slider('配属枠の何%以上が埋まった科を表示するか', min_value=0.0, max_value=1.0, value=0.7, step=0.05)
# 合致科抽出
depts_full = assign_dept.merge(cap_dept,on='department')
reached = depts_full[depts_full['assigned_count'] >= depts_full['capacity']*threshold]['department']
# 最大通過順位計算
max_rank = (df_long2[df_long2['department'].isin(reached)].groupby('department',as_index=False)['lottery_order'].max()
            .rename(columns={'lottery_order':'昨年の最大通過順位'}).sort_values('昨年の最大通過順位'))
# バーグラフ（人気な科を上に表示）
chart2 = (
    alt.Chart(max_rank)
    .mark_bar()
    .encode(
        x=alt.X('昨年の最大通過順位:Q', title='最大通過順位'),
        y=alt.Y('department:N', sort=alt.EncodingSortField(field='昨年の最大通過順位', order='ascending'), title='診療科')
    )
    .properties(width=700, height=max(300, len(max_rank)*25))
)
st.altair_chart(chart2, use_container_width=True)
