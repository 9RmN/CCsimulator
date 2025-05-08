import pandas as pd

# --- データ読み込み（student_id をすべて文字列型で統一） ---
responses = pd.read_csv("responses.csv", dtype=str)
lottery   = pd.read_csv("lottery_order.csv", dtype={'student_id':str, 'lottery_order':int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# student_id の正規化（先頭ゼロ除去）
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# 希望列の特定
hope_columns = [col for col in responses.columns if col.startswith("hope_")]
MAX_HOPES    = max(int(col.split("_")[1]) for col in hope_columns)

# term一覧
TERM_LABELS = ["term_1", "term_2", "term_3", "term_4"]

# 初期配属記録
assignment_result = []
student_assigned_departments = {}

# 各 term ごとに配属処理
for term_label in TERM_LABELS:
    # term_map を student_id と term（数値）で取得
    term_map = terms_df[["student_id", term_label]].rename(columns={term_label: "term"})
    # マージ（キー student_id は両方文字列）
    merged = (
        responses
        .merge(term_map, on="student_id")
        .merge(lottery, on="student_id")
        .sort_values("lottery_order")
    )

    # capacity キー辞書作成
    cap_dict = {}
    for _, row in capacity_df.iterrows():
        dept = row["hospital_department"]
        for term in capacity_df.columns[1:]:
            # 欠損値は 0 とみなす
            val = row[term]
            cap_dict[(dept, term)] = int(val) if not pd.isna(val) else 0
        dept = row["hospital_department"]
        for term in capacity_df.columns[1:]:
            cap_dict[(dept, term)] = int(row[term])

    # 各学生の配属
    for _, row in merged.iterrows():
        sid = row["student_id"]
        term = row["term"]
        assigned_depts = student_assigned_departments.get(sid, set())
        assigned = False

        # 希望順ループ
        for i in range(1, MAX_HOPES + 1):
            dept_key = f"hope_{i}"
            dept = row.get(dept_key)
            if pd.isna(dept) or dept in assigned_depts:
                continue
            cap_key = (dept, f"term_{term}")
            if cap_dict.get(cap_key, 0) > 0:
                cap_dict[cap_key] -= 1
                assignment_result.append({
                    "student_id": sid,
                    "term": term,
                    "assigned_department": dept,
                    "hope_rank": i
                })
                assigned_depts.add(dept)
                student_assigned_departments[sid] = assigned_depts
                assigned = True
                break

        # 希望が割り当てられなかった場合
        if not assigned:
            assignment_result.append({
                "student_id": sid,
                "term": term,
                "assigned_department": "未配属",
                "hope_rank": None
            })

# 結果の保存
df_result = pd.DataFrame(assignment_result)
df_result.to_csv("initial_assignment_result.csv", index=False)
print("✅ 初期配属（1人1科1term制約付き）完了")
