import pandas as pd
import ast

# --- データ読み込み ---
responses = pd.read_csv("responses.csv", dtype=str)
lottery = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df = pd.read_csv("student_terms.csv", dtype=str)

# student_id の正規化
for df in (responses, lottery, terms_df):
    df['student_id'] = df['student_id'].str.lstrip('0')

# --- 希望列の特定 ---
hope_columns = [col for col in responses.columns if col.startswith('hope_')]
MAX_HOPES = max(int(col.split('_')[1]) for col in hope_columns)

# --- term 列ラベルと学生タームマップ ---
TERM_LABELS = [col for col in terms_df.columns if col.startswith('term_')]
student_terms = {
    row['student_id']: [int(row[col]) for col in TERM_LABELS if pd.notna(row[col])]
    for _, row in terms_df.iterrows()
}

# --- 指定タームマップ作成 ---
term_prefs = {}
for _, row in responses.iterrows():
    sid = row['student_id']
    prefs = {}
    for i in range(1, MAX_HOPES + 1):
        dept = row.get(f"hope_{i}")
        raw = row.get(f"hope_{i}_terms")
        if pd.isna(dept) or pd.isna(raw):
            continue
        try:
            terms_list = ast.literal_eval(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        prefs[dept] = [int(t) for t in terms_list if str(t).isdigit()]
    term_prefs[sid] = prefs

# --- capacity 辞書化 ---
cap = {}
cap_cols = [c for c in capacity_df.columns if c.startswith('term_')]
for _, row in capacity_df.iterrows():
    dept = row['hospital_department']
    for col in cap_cols:
        term_num = int(col.split('_')[1])
        cap[(dept, term_num)] = int(row[col]) if not pd.isna(row[col]) else 0

# --- 初期配属記録 ---
assignment_result = []
student_assigned_departments = {}

# 各タームスロットごとの処理
for term_label in TERM_LABELS:
    # student_terms の term_label から実ターム番号を取得
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

    # 学生ごとの処理
    for _, row in merged.iterrows():
        sid = row['student_id']
        term = row['term']
        used_depts = student_assigned_departments.get(sid, set())
        assigned = False

        # 第1～MAX_HOPES希望までループ
        for i in range(1, MAX_HOPES + 1):
            dept = row.get(f"hope_{i}")
            if pd.isna(dept) or dept in used_depts:
                continue

            # 指定ターム優先のallowedリストを作成
            default_terms = student_terms.get(sid, [])
            dept_specific = term_prefs.get(sid, {}).get(dept, [])
            if dept_specific:
                # 指定タームを先に、以降はデフォルトタームを追加
                allowed = dept_specific + [t for t in default_terms if t not in dept_specific]
            else:
                # 指定タームなしなら全タームを対象
                allowed = default_terms

            # 現在のslot term がallowedに含まれるかを確認
            if term not in allowed:
                continue

            # 空きがあれば割当
            cap_key = (dept, term)
            if cap.get(cap_key, 0) > 0:
                cap[cap_key] -= 1
                assignment_result.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': dept,
                    'hope_rank': i
                })
                used_depts.add(dept)
                student_assigned_departments[sid] = used_depts
                assigned = True
                break

        # すべての希望で配属できなかった場合
        if not assigned:
            assignment_result.append({
                'student_id': sid,
                'term': term,
                'assigned_department': '未配属',
                'hope_rank': None
            })

# 結果保存
pd.DataFrame(assignment_result).to_csv('initial_assignment_result.csv', index=False)
print("✅ 初期配属（1人1科1term制約付き）完了")
