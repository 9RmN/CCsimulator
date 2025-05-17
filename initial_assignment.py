import pandas as pd
import ast

# --- データ読み込み ---
responses   = pd.read_csv("responses.csv", dtype=str)
lottery     = pd.read_csv("lottery_order.csv", dtype={"student_id":str, "lottery_order":int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# student_id の正規化
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# --- 希望列の特定 ---
hope_columns = [col for col in responses.columns if col.startswith("hope_")]
MAX_HOPES    = max(int(col.split("_")[1]) for col in hope_columns)

# --- term 列ラベル ---
TERM_LABELS = [col for col in terms_df.columns if col.startswith('term_')]

# --- 学生ごとのタームマップ ---
student_terms = {
    row['student_id']: [int(row[col]) for col in TERM_LABELS if pd.notna(row[col])]
    for _, row in terms_df.iterrows()
}

# --- 科ごとの指定タームマップ作成 ---
# responses 側に hope_{i}_terms 列が追加されている前提
term_prefs = {}
for _, row in responses.iterrows():
    sid = row['student_id']
    prefs = {}
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        raw = row.get(f"hope_{i}_terms")
        if pd.isna(dept) or pd.isna(raw):
            continue
        # リスト形式の文字列をパース
        try:
            terms_list = ast.literal_eval(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        prefs[dept] = [int(t) for t in terms_list if str(t).isdigit()]
    term_prefs[sid] = prefs

# --- 初期配属記録 ---
assignment_result = []
student_assigned_departments = {}

# 各 term ごとに配属処理
for term_label in TERM_LABELS:
    # term_map を student_id と term（数値）で取得
    term_map = (
        terms_df[['student_id', term_label]]
        .rename(columns={term_label: 'term'})
    )
    term_map['term'] = term_map['term'].astype(int)

    # マージ & 抽選順ソート
    merged = (
        responses
        .merge(term_map, on='student_id')
        .merge(lottery, on='student_id')
        .sort_values('lottery_order')
    )

    # capacity キー辞書作成
    cap_dict = {}
    for _, row in capacity_df.iterrows():
        dept = row['hospital_department']
        for tl in TERM_LABELS:
            cap_dict[(dept, int(tl.split('_')[1]))] = (
                int(row[tl]) if not pd.isna(row[tl]) else 0
            )

    # 各学生の配属
    for _, row in merged.iterrows():
        sid = row['student_id']
        term = row['term']
        assigned_depts = student_assigned_departments.get(sid, set())
        assigned = False

        # 今回の学生が利用できるタームリスト
        # ただし、各希望科ごとに dept-specific prefs を優先
        for i in range(1, MAX_HOPES + 1):
            dept = row.get(f"hope_{i}")
            if pd.isna(dept) or dept in assigned_depts:
                continue

            # 課せられたターム条件を取得
            allowed = term_prefs.get(sid, {}).get(dept,
                        student_terms.get(sid, []))
            # もしこの term が許可リストにないならスキップ
            if term not in allowed:
                continue

            cap_key = (dept, term)
            if cap_dict.get(cap_key, 0) > 0:
                cap_dict[cap_key] -= 1
                assignment_result.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': dept,
                    'hope_rank': i
                })
                assigned_depts.add(dept)
                student_assigned_departments[sid] = assigned_depts
                assigned = True
                break

        # 希望が割り当てられなかった場合
        if not assigned:
            assignment_result.append({
                'student_id': sid,
                'term': term,
                'assigned_department': '未配属',
                'hope_rank': None
            })

# 結果の保存
pd.DataFrame(assignment_result).to_csv(
    'initial_assignment_result.csv', index=False
)
print("✅ 初期配属（1人1科1term制約付き with term preferences）完了")
