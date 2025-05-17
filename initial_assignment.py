import pandas as pd

# --- データ読み込み ---
responses   = pd.read_csv("responses.csv", dtype=str)
lottery     = pd.read_csv("lottery_order.csv", dtype={"student_id":str, "lottery_order":int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# 正規化
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# hope列取得
hope_cols = [c for c in responses.columns if c.startswith('hope_')]
MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)

# term列ラベル取得 & 学生タームマップ
term_labels = [col for col in terms_df.columns if col.startswith('term_')]
student_terms_map = {
    row['student_id']: [int(row[col]) for col in term_labels if pd.notna(row[col])]
    for _, row in terms_df.iterrows()
}

# term_prefs: 学生ごと科ごとの指定タームリスト
term_prefs = {}
for _, row in responses.iterrows():
    sid = row['student_id']
    # parse hope_{i}_terms as list
    dmap = {}
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        raw = row.get(f"hope_{i}_terms")
        if pd.isna(dept) or pd.isna(raw):
            continue
        # raw is string of list
        try:
            terms = pd.eval(raw)
        except:
            continue
        dmap[dept] = [int(t) for t in terms if str(t).isdigit()]
    term_prefs[sid] = dmap

# capacity dict 初期化
cap_dict = {}
for _, r in capacity_df.iterrows():
    dept = r['hospital_department']
    for tcol in term_labels:
        cap_dict[(dept, int(tcol.split('_')[1]))] = int(r[tcol]) if not pd.isna(r[tcol]) else 0

# 学生をLottery順にソート
merged_students = (
    responses
    .merge(lottery, on='student_id')
    .sort_values('lottery_order')
    .reset_index(drop=True)
)

assignment = []
student_assigned = {sid: set() for sid in merged_students['student_id']}

# Student→Hope→Term ループ
for _, row in merged_students.iterrows():
    sid = row['student_id']
    used = student_assigned[sid]
    assigned = False
    # 各希望順
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        if pd.isna(dept) or dept in used:
            continue
        # 許可ターム取得
        prefs = term_prefs.get(sid, {}).get(dept, student_terms_map.get(sid, []))
        # 希望ターム or 全タームから選択
        for term in prefs:
            key = (dept, term)
            if cap_dict.get(key, 0) > 0:
                # 割当
                cap_dict[key] -= 1
                used.add(dept)
                assignment.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': dept,
                    'hope_rank': i
                })
                assigned = True
                break
        if assigned:
            break
    # 全希望ループ後に未割当なら未配属
    if not assigned:
        # フォールバックなし→未配属
        for t in student_terms_map.get(sid, []):
            assignment.append({
                'student_id': sid,
                'term': t,
                'assigned_department': '未配属',
                'hope_rank': None
            })
        # 学生ごとのタームを一度まとめた後の終了

# CSV出力
pd.DataFrame(assignment).to_csv('initial_assignment_result.csv', index=False)
print('✅ 初期配属(Student→Hope→Term) 完了')
