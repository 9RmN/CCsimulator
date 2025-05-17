import pandas as pd

# --- データ読み込み ---
responses   = pd.read_csv("responses.csv", dtype=str)
lottery     = pd.read_csv("lottery_order.csv", dtype={"student_id":str, "lottery_order":int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# student_id 正規化
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# --- hope 列の特定 ---
hope_cols = [c for c in responses.columns if c.startswith('hope_')]
MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)

# --- term 列と student_terms_map ---
term_cols = [col for col in terms_df.columns if col.startswith('term_')]
student_terms_map = {
    row['student_id']: [int(row[c]) for c in term_cols if pd.notna(row[c])]
    for _, row in terms_df.iterrows()
}

# --- term_prefs: sid -> { dept: [terms] } ---
term_prefs = {}
for _, row in responses.iterrows():
    sid = row['student_id']
    prefs = {}
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        raw = row.get(f"hope_{i}_terms")
        if pd.isna(dept) or pd.isna(raw):
            continue
        try:
            terms = pd.eval(raw)
        except:
            continue
        prefs[dept] = [int(t) for t in terms if str(t).isdigit()]
    term_prefs[sid] = prefs

# --- capacity 初期化 ---
cap_dict = {}
for _, r in capacity_df.iterrows():
    dept = r['hospital_department']
    for c in term_cols:
        term_num = int(c.split('_')[1])
        cap_dict[(dept, term_num)] = int(r[c]) if not pd.isna(r[c]) else 0

# --- 学生を lottery_order 順にソート ---
students = (
    responses
    .merge(lottery, on='student_id')
    .sort_values('lottery_order')
    .reset_index(drop=True)
)

# --- 配属処理: Student→Hope→Term ---
assignment = []
for _, row in students.iterrows():
    sid = row['student_id']
    used_depts = set()
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        if pd.isna(dept) or dept in used_depts:
            continue
        # 許可ターム取得
        allowed = term_prefs.get(sid, {}).get(dept, student_terms_map.get(sid, []))
        placed = False
        for term in allowed:
            key = (dept, term)
            if cap_dict.get(key, 0) > 0:
                cap_dict[key] -= 1
                used_depts.add(dept)
                assignment.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': dept,
                    'hope_rank': i
                })
                placed = True
                break
        # 割当できなければ未配属として記録
        if not placed:
            assignment.append({
                'student_id': sid,
                'term': None,
                'assigned_department': '未配属',
                'hope_rank': i
            })

# --- 結果出力 ---
pd.DataFrame(assignment).to_csv('initial_assignment_result.csv', index=False)
print('✅ 初期配属(全希望考慮) 完了')
