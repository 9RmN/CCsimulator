import pandas as pd
import re

# --- 1. ターム指定パース関数 ---
def parse_term_list(raw, default_terms):
    """
    raw: responses.csv の hope_n_terms フィールド
    default_terms: その学生の基本４タームリスト
    戻り値: 指定タームのリスト（昇順）、指定なし／不正入力時は None
    """
    if pd.isna(raw) or not str(raw).strip():
        return None
    # 「,」「;」「 」などで分割
    tokens = re.split(r"[;, \t]+", str(raw).strip())
    # 数字のみ抽出
    terms = [int(t) for t in tokens if t.isdigit()]
    # default_terms のサブセットだけ残す
    valid = [t for t in terms if t in default_terms]
    if not valid:
        return None
    return sorted(set(valid))


# --- データ読み込み ---
responses     = pd.read_csv("responses.csv",        dtype=str)
lottery       = pd.read_csv("lottery_order.csv",    dtype={'student_id': str, 'lottery_order': int})
capacity_df   = pd.read_csv("department_capacity.csv")
terms_df      = pd.read_csv("student_terms.csv",     dtype=str)

# student_id の正規化
for df in (responses, lottery, terms_df):
    df['student_id'] = df['student_id'].str.lstrip('0')

# term 列ラベルと希望数上限を取得
TERM_LABELS = [c for c in terms_df.columns if c.startswith("term_")] 
MAX_HOPES   = max(
    int(c.split("_")[1])
    for c in responses.columns
    if c.startswith("hope_") and not c.endswith("_terms")
)

# --- student_terms_map の構築 ---
# terms_df は term_1～term_4 の各列に 1～11 が入っている想定
student_terms_map = {
    row["student_id"]: [int(row[c]) for c in TERM_LABELS]
    for _, row in terms_df.iterrows()
}

# --- 2. hope_n_terms をパースして辞書化 ---
term_prefs = {}
for _, row in responses.iterrows():
    sid          = row["student_id"]
    default_terms = student_terms_map[sid]
    prefs        = {}
    for i in range(1, MAX_HOPES + 1):
        dept = row.get(f"hope_{i}")           # 例: "本院-内科（呼吸器）"
        raw  = row.get(f"hope_{i}_terms")     # 例: "2,5"
        if pd.isna(dept) or not str(dept).strip() or pd.isna(raw):
            continue
        # parse_term_list で default_terms のサブセットとして正規化
        valid_terms = parse_term_list(raw, default_terms)
        if valid_terms:
            prefs[dept] = valid_terms
    term_prefs[sid] = prefs

# --- 3. capacity 辞書化 ---
cap = {}
cap_cols = [c for c in capacity_df.columns if c.startswith("term_")]
for _, row in capacity_df.iterrows():
    dept = row["hospital_department"]        # カラム名に注意
    for col in cap_cols:
        term_num       = int(col.split("_")[1])
        cap[(dept,term_num)] = int(row[col]) if not pd.isna(row[col]) else 0

# --- 初期配属処理 ---
assignment_result = []
student_assigned_departments = {}

for term_label in TERM_LABELS:
    # 各学生の term_label → 実ターム番号 にマップ
    term_map = (
        terms_df[["student_id", term_label]]
        .rename(columns={term_label: "term"})
        .astype({"term": int})
    )
    merged = (
        responses
        .merge(term_map, on="student_id")
        .merge(lottery,   on="student_id")
        .sort_values("lottery_order")
    )

    for _, row in merged.iterrows():
        sid   = row["student_id"]
        term  = row["term"]
        used  = student_assigned_departments.get(sid, set())
        assigned = False

        for i in range(1, MAX_HOPES+1):
            dept = row.get(f"hope_{i}")
            if pd.isna(dept) or not str(dept).strip() or dept == "-":
                continue

            # 指定タームがあればそのリストのみ、なければ default_terms
            specific = term_prefs[sid].get(dept)
            allowed  = specific if specific is not None else student_terms_map[sid]

            if term not in allowed:
                continue

            key = (dept, term)
            if cap.get(key, 0) > 0:
                # 割当
                cap[key] -= 1
                assignment_result.append({
                    "student_id": sid,
                    "term":       term,
                    "assigned_department": dept,
                    "hope_rank": i
                })
                used.add(dept)
                student_assigned_departments[sid] = used
                assigned = True
                break

        if not assigned:
            assignment_result.append({
                "student_id": sid,
                "term":       term,
                "assigned_department": "未配属",
                "hope_rank": None
            })

# --- 結果出力 ---
pd.DataFrame(assignment_result).to_csv("initial_assignment_result.csv", index=False)
print("✅ 初期配属（1人1科1term制約） 完了")
