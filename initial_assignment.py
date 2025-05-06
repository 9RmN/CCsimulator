
import pandas as pd

# データ読み込み
responses = pd.read_csv("responses.csv")
lottery = pd.read_csv("lottery_order.csv")
capacity_df = pd.read_csv("department_capacity.csv")
terms_df = pd.read_csv("student_terms.csv")

# 希望列の特定
hope_columns = [col for col in responses.columns if col.startswith("hope_")]
MAX_HOPES = max([int(col.split("_")[1]) for col in hope_columns])

# term一覧
TERM_LABELS = ["term_1", "term_2", "term_3", "term_4"]

# 初期配属記録
assignment_result = []
student_assigned_departments = {}

# 各 term ごとに配属処理
for term_label in TERM_LABELS:
    term_map = terms_df[["student_id", term_label]].rename(columns={term_label: "term"})
    responses_term = responses.merge(term_map, on="student_id")
    merged = responses_term.merge(lottery, on="student_id").sort_values("lottery_order")

    cap_dict = {}
    for _, row in capacity_df.iterrows():
        dept = row["hospital_department"]
        for term in capacity_df.columns[1:]:
            cap_dict[(dept, term)] = row[term]

    for _, row in merged.iterrows():
        sid = row["student_id"]
        term = row["term"]
        assigned = False
        assigned_depts = student_assigned_departments.get(sid, set())

        for i in range(1, MAX_HOPES + 1):
            dept = row.get(f"hope_{i}")
            if pd.isna(dept) or dept in assigned_depts:
                continue
            key = (dept, f"term_{term}")
            if cap_dict.get(key, 0) > 0:
                cap_dict[key] -= 1
                assignment_result.append({
                    "student_id": sid,
                    "term": term,
                    "assigned_department": dept,
                    "hope_rank": i
                })
                assigned = True
                assigned_depts.add(dept)
                student_assigned_departments[sid] = assigned_depts
                break

        if not assigned:
            assignment_result.append({
                "student_id": sid,
                "term": term,
                "assigned_department": "未配属",
                "hope_rank": None
            })

# 保存
df_result = pd.DataFrame(assignment_result)
df_result.to_csv("initial_assignment_result.csv", index=False)
print("✅ 初期配属（1人1科1term制約付き）完了")
