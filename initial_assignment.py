import pandas as pd
import re

# --- データ読み込み ---
responses   = pd.read_csv("responses.csv", dtype=str)
lottery     = pd.read_csv("lottery_order.csv", dtype={"student_id":str, "lottery_order":int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# student_id の正規化
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# hope_n 列のみを特定
hope_columns = [col for col in responses.columns if re.fullmatch(r"hope_\d+", col)]
MAX_HOPES = max(int(col.split('_')[1]) for col in hope_columns)

# --- 複数ターム希望の取り込み ---
# responses.csv に生成された hope_n_terms リスト列を用いる
term_prefs = {}
for _, row in responses.iterrows():
    sid = row['student_id']
    prefs = []
    for i in range(1, MAX_HOPES+1):
        dept = row.get(f"hope_{i}")
        terms_list = row.get(f"hope_{i}_terms")
        if pd.notna(dept) and isinstance(terms_list, list):
            for t in terms_list:
                try:
                    prefs.append((dept, int(t)))
                except ValueError:
                    continue
    term_prefs[sid] = prefs

# term 列ラベルのリスト
TERM_LABELS = [col for col in terms_df.columns if col.startswith('term_')]

# 初期配属結果格納用
assignment_result = []
student_assigned = {}

# term ごとにループ
for term_label in TERM_LABELS:
    # term_map: student_id と期番号 (int) を持つデータフレーム
    term_map = terms_df[['student_id', term_label]].rename(columns={term_label:'term'})
    term_map['term'] = term_map['term'].astype(int)

    # merge して lottery_order ソート
    merged = (
        responses
        .merge(term_map, on='student_id')
        .merge(lottery, on='student_id')
        .sort_values('lottery_order')
    )

    # capacity 辞書化
    cap_dict = {}
    for _, cap_row in capacity_df.iterrows():
        dept = cap_row['hospital_department']
        for tcol in TERM_LABELS:
            cap_dict[(dept, tcol)] = int(cap_row[tcol]) if pd.notna(cap_row[tcol]) else 0

    # 学生ごと配属
    for _, row in merged.iterrows():
        sid = row['student_id']
        term = row['term']  # int
        allowed = term_prefs.get(sid, [])
        used = student_assigned.get(sid, set())
        placed = False

        for i in range(1, MAX_HOPES+1):
            dept = row.get(f"hope_{i}")
            if pd.isna(dept) or dept in used:
                continue
            # ターム指定があればフィルタ
            if allowed and (dept, term) not in allowed:
                continue
            cap_key = (dept, f"term_{term}")
            if cap_dict.get(cap_key, 0) > 0:
                cap_dict[cap_key] -= 1
                used.add(dept)
                student_assigned[sid] = used
                assignment_result.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': dept,
                    'hope_rank': i
                })
                placed = True
                break

        if not placed:
            assignment_result.append({
                'student_id': sid,
                'term': term,
                'assigned_department': '未配属',
                'hope_rank': None
            })

# 結果保存
pd.DataFrame(assignment_result).to_csv('initial_assignment_result.csv', index=False)
print('✅ 初期配属（1人1科1term制約付き）完了')
