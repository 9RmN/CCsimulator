import os
import streamlit as st
import pandas as pd
import hashlib
import altair as alt

# --- Streamlit 自動リフレッシュ ---
st.markdown(
    '<meta http-equiv="refresh" content="300">',
    unsafe_allow_html=True,
)

# --- セッションステート 初期化 ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = ''

# --- Pepper の取得 ---
# Top-level: 大文字・小文字両方チェック
pepper = st.secrets.get("PEPPER") or st.secrets.get("pepper")
if pepper:
    st.info("🔒 Pepper を st.secrets から読み込みました")
else:
    # 次に [auth] セクション内をチェック（大文字・小文字両方）
    auth_sec = st.secrets.get("auth", {})
    pepper = auth_sec.get("PEPPER") or auth_sec.get("pepper")
    if pepper:
        st.info("🔒 Pepper を st.secrets['auth'] から読み込みました")
# 最後に環境変数をフォールバック（大文字・小文字両方）
if not pepper:
    pepper = os.environ.get('PEPPER') or os.environ.get('pepper')
    if pepper:
        st.info("🔒 Pepper を環境変数から読み込みました")
# 見つからない場合は停止
if not pepper:
    st.error("⚠️ Pepper が設定されていません。認証に失敗します。")
    st.stop()

@st.cache_data(ttl=60)
def load_data():
    prob_df = pd.read_csv(
        "probability_montecarlo_combined.csv",
        dtype={'student_id': str}
    )
    auth_df = pd.read_csv(
        "auth.csv",
        dtype={'student_id': str, 'password_hash': str, 'role': str}
    )
    rank_df = pd.read_csv("popular_departments_rank_combined.csv")
    terms_df = pd.read_csv(
        "student_terms.csv",
        dtype={'student_id': str}
    )
    responses_df = pd.read_csv(
        "responses.csv",
        dtype={'student_id': str}
    )

    # 正規化
    responses_df['student_id'] = responses_df['student_id'].str.lstrip('0')
    prob_df['student_id']      = prob_df['student_id'].str.lstrip('0')
    terms_df['student_id']     = terms_df['student_id'].str.lstrip('0')

    # インデックス設定
    responses_df.set_index('student_id', inplace=True)
    prob_df.set_index('student_id', inplace=True)
    terms_df.set_index('student_id', inplace=True)

    return prob_df, auth_df, rank_df, terms_df, responses_df

# --- データロード ---
prob_df, auth_df, rank_df, terms_df, responses_df = load_data()

# --- ユーザー認証関数 ---
def verify_user(sid, pwd):
    if not sid.isdigit():
        return False
    row = auth_df[
        (auth_df['student_id'] == sid) &
        (auth_df['role'].isin(['student','admin']))
    ]
    if row.empty:
        return False
    hashed = hashlib.sha256((pwd + pepper).encode()).hexdigest()
    return hashed == row.iloc[0]['password_hash']

# --- ログイン画面 ---
if not st.session_state['authenticated']:
    st.title("🔐 ログイン")
    uid = st.text_input("User ID", value="", key="login_uid")
    pwd = st.text_input("パスワード", type="password", key="login_pwd")
    if st.button("ログイン"):
        if verify_user(uid, pwd):
            st.session_state['authenticated'] = True
            st.session_state['user_id'] = uid
            st.success(f"認証成功: user_id={uid}")
        else:
            st.error("認証失敗：IDまたはパスワードが違います。")
    st.stop()

# --- 認証後コンテンツ ---
sid = st.session_state['user_id']
st.title(f"🎓 選択科アンケート (user_id={sid})")

# 回答率表示
total_students    = len(terms_df)
answered_students = responses_df.shape[0]
answered_ratio     = answered_students / total_students * 100
st.markdown(f"🧾 **回答者：{answered_students} / {total_students}人**（{answered_ratio:.1f}%）")
if answered_ratio < 70:
    st.warning("⚠️ 回答者が少ないため、結果がまだ不安定です。")

# 利用データ取得
resp_row = responses_df.loc[sid] if sid in responses_df.index else pd.Series()
prob_row = prob_df.loc[sid]      if sid in prob_df.index else pd.Series()

# —————— 希望科＆通過確率表示 ——————
st.subheader("🎯 希望科通過確率一覧 (第1〜20希望)")
display = []
for i in range(1, 21):
    hope_col = f"hope_{i}"
    prob_col = f"hope_{i}_確率"
    dept = resp_row.get(hope_col)
    if not dept or pd.isna(dept):
        continue
    prob = prob_row.get(prob_col)
    display.append({
        '希望順位': f"第{i}希望: {dept}",
        '通過確率': prob
    })
df_disp = pd.DataFrame(display)

# 色付け関数
def color_prob(val):
    try:
        num = float(val)
        if num >= 80: return 'background-color:#d4edda'
        if num >= 50: return 'background-color:#fff3cd'
        if num > 0:   return 'background-color:#f8d7da'
    except:
        pass
    return ''

if '通過確率' in df_disp.columns:
    st.dataframe(
        df_disp.style.map(color_prob, subset=['通過確率']),
        use_container_width=True
    )
else:
    st.dataframe(df_disp, use_container_width=True)

# 人気診療科トップ15表示
st.subheader("🔥 人気診療科トップ15 (抽選順位中央値)")
median_col = rank_df.columns[1]
rank_df[median_col] = pd.to_numeric(rank_df[median_col], errors='coerce')
top15 = rank_df.groupby(rank_df.columns[0])[median_col].median().nsmallest(15)
chart_df = top15.reset_index().rename(
    columns={rank_df.columns[0]: '診療科', median_col: '抽選順位中央値'}
)
top15_df = chart_df.sort_values('抽選順位中央値')
chart = alt.Chart(top15_df).mark_bar().encode(
    x=alt.X('抽選順位中央値:Q', title='抽選順位中央値'),
    y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending'), title=None)
).properties(height=400)
text = alt.Chart(top15_df).mark_text(align='left', dx=3, baseline='middle').encode(
    y=alt.Y('診療科:N', sort=alt.EncodingSortField(field='抽選順位中央値', order='ascending')),
    x=alt.X('抽選順位中央値:Q'),
    text=alt.Text('抽選順位中央値:Q')
)

st.altair_chart(chart + text, use_container_width=True)
