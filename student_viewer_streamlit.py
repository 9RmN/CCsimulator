import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
import altair as alt
import importlib
# Ensure current directory is in module path
sys.path.insert(0, os.getcwd())

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
    first_choice_df = pd.read_csv("first_choice_probabilities.csv", dtype={'student_id':str})
    # 左ゼロ除去
    for df in [responses_df,prob_df,terms_df,auth_df]:
        df['student_id'] = df['student_id'].str.lstrip('0')
    # インデックス設定
    responses_df.set_index('student_id',inplace=True)
    prob_df.set_index('student_id',inplace=True)
    terms_df.set_index('student_id',inplace=True)
    auth_df.set_index('student_id',inplace=True)
    first_choice_df['student_id'] = first_choice_df['student_id'].str.lstrip('0')
    first_choice_df.set_index('student_id', inplace=True)
    return prob_df, auth_df, rank_df, terms_df, responses_df, first_choice_df

prob_df, auth_df, rank_df, terms_df, responses_df, first_choice_df = load_data()

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
    sid = st.text_input("学生番号", key="login_uid")
    pwd = st.text_input("パスワード", type="password", key="login_pwd")
    if st.button("ログイン"):
        if verify_user(sid, pwd):
            st.session_state['authenticated'] = True
            st.session_state['user_id'] = sid.lstrip('0')
        else:
            st.error("認証に失敗しました。")
    # ここで st.stop() すると、認証成功後に
    # 同じリクエストで下のコードが続けて実行されます
    st.stop()

# --- 認証後メイン画面 ---
sid = st.session_state['user_id']
st.title(f"🎓 選択科アンケート (学生番号={sid})")

# 回答率表示
all_count = len(terms_df)
answered_count = responses_df.shape[0]
ratio = answered_count / all_count * 100
st.markdown(f"🧾 **回答者：{answered_count}/{all_count} 人**（{ratio:.1f}%）")
if ratio < 70:
    st.warning("⚠️ 回答者が少ないため結果が不安定です。回答を促してください。")

# --- 通過確率比較テーブル (幅調整付き) ---
st.subheader("🌀 通過確率比較 (順位あり / 全て第1希望)")

# 1) データ収集
rows = []
for i in range(1, 21):
    hope = responses_df.loc[sid].get(f"hope_{i}")
    if not hope:
        continue

    # 順位ありシミュレーションの確率
    ranked = prob_df.loc[sid].get(f"hope_{i}_確率")
    ranked_str = f"{int(ranked)}%" if pd.notna(ranked) else ""

    # 全て第1希望時の確率
    flat_row = first_choice_df[first_choice_df["希望科"] == hope]
    flat_str = ""
    if not flat_row.empty:
        pct = flat_row["通過確率"].iloc[0]
        flat_str = f"{pct:.1f}%"

    rows.append({
        "希望":           f"{i}: {hope}",
        "順位あり":       ranked_str,
        "全て第1希望":    flat_str
    })

# 2) DataFrame 作成＆インデックス設定
df = pd.DataFrame(rows).set_index("希望")

# 3) 列幅スタイル設定
styled = df.style.set_table_styles([
    # インデックス（希望）を広く
    {
        'selector': 'th.row_heading, td.row_heading',
        'props': [('min-width', '300px'), ('text-align', 'left')]
    },
    # 「順位あり」列を狭く
    {
        'selector': 'th.col_heading.col1, td.col1',
        'props': [('min-width', '80px'), ('text-align', 'center')]
    },
    # 「全て第1希望」列も狭く
    {
        'selector': 'th.col_heading.col2, td.col2',
        'props': [('min-width', '80px'), ('text-align', 'center')]
    },
])

# 4) 表示
st.write(styled)

st.markdown("""
**説明:**
- **順位あり**: 学生が実際に入力した希望順位をもとに、各順位で通過できる確率をシミュレーションしたものです。合計確率が100%になります。
- **全て第1希望**: すべての希望を第1希望として仮定し、他学生との競合を均一化して計算した通過確率です。純粋にその科に配属されそうかどうかが判定できます。
""")

# --- 希望人数表示 ---
st.subheader("📋 第1～3希望人数 (科ごと・Term1～Term11)")
try:
    dept_summary = pd.read_csv("department_summary.csv", index_col=0)
    st.dataframe(dept_summary, use_container_width=True)
except FileNotFoundError:
    st.warning("department_summary.csv が見つかりません。")

# --- 人気診療科トップ15 ---
st.subheader("🔥 人気診療科トップ15 (抽選順位中央値)")
median_col = rank_df.columns[1]
rank_df[median_col] = pd.to_numeric(rank_df[median_col], errors='coerce')
top15 = rank_df.groupby(rank_df.columns[0])[median_col].median().nsmallest(15)
chart_df = top15.reset_index().rename(columns={rank_df.columns[0]: '診療科', median_col: '抽選順位中央値'})
# ベースチャートと数値ラベル
base_chart = alt.Chart(chart_df).mark_bar().encode(
    x=alt.X('抽選順位中央値:Q', title='抽選順位中央値'),
    y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending'), title=None)
).properties(width=700, height=max(300, len(chart_df)*25))
text = base_chart.mark_text(align='left', baseline='middle', dx=3).encode(text=alt.Text('抽選順位中央値:Q'))
layered = alt.layer(base_chart, text).configure_axis(labelFontSize=10, titleFontSize=14, labelAngle=0, labelAlign='right')
st.altair_chart(layered, use_container_width=True)

# --- 昨年：一定割合以上配属された科の最大通過順位 ---
st.subheader("🔖 昨年：一定割合以上配属された科の最大通過順位")
# データ読み込み
hist_df = pd.read_csv("2024配属結果.csv", dtype={'student_id':str, 'lottery_order':int})
cap_df  = pd.read_csv("department_capacity.csv")
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
