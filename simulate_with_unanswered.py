
import pandas as pd
import random
from collections import defaultdict

responses_base = pd.read_csv("responses.csv")
lottery = pd.read_csv("lottery_order.csv")
capacity_df = pd.read_csv("department_capacity.csv")
terms_df = pd.read_csv("student_terms.csv")

hope_columns = [col for col in responses_base.columns if col.startswith("hope_")]
MAX_HOPES = max([int(col.split("_")[1]) for col in hope_columns])
TERM_LABELS = ["term_1", "term_2", "term_3", "term_4"]

answered_ids = set(responses_base["student_id"])
all_ids = set(terms_df["student_id"])
unanswered_ids = list(all_ids - answered_ids)
unanswered_df = lottery[lottery["student_id"].isin(unanswered_ids)]

def calculate_popularity(responses):
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES + 1):
        weight = MAX_HOPES + 1 - i
        for dept in responses[f"hope_{i}"].dropna():
            popularity[dept] += weight
    return popularity

popularity = calculate_popularity(responses_base)

def generate_unanswered(popularity, unanswered_df):
    total = sum(popularity.values())
    department_prob = {k: v / total for k, v in popularity.items()}
    depts = list(department_prob.keys())
    weights = list(department_prob.values())
    generated_rows = []

    for sid in unanswered_df["student_id"]:
        hopes = random.choices(depts, weights=weights, k=MAX_HOPES)
        row = {'student_id': sid}
        for i, dept in enumerate(hopes):
            row[f"hope_{i+1}"] = dept
        generated_rows.append(row)

    return pd.DataFrame(generated_rows)

if unanswered_df.empty:
    print("✅ 全員回答済のため、未回答補完スキップ")
    responses_all = responses_base.copy()
else:
    print(f"⚠️ 未回答者 {len(unanswered_df)}名、人気スコアから希望生成")
    generated = generate_unanswered(popularity, unanswered_df)
    generated["student_id"] = unanswered_df["student_id"].values
    responses_all = pd.concat([responses_base, generated], ignore_index=True)

assignment_result = []
cap_dict = {}
for _, row in capacity_df.iterrows():
    dept = row["hospital_department"]
    for term in capacity_df.columns[1:]:
        cap_dict[(dept, term)] = row[term]

student_assigned_departments = {}

for term_label in TERM_LABELS:
    term_map = terms_df[["student_id", term_label]].rename(columns={term_label: "term"})
    responses_term = responses_all.merge(term_map, on="student_id")
    merged = responses_term.merge(lottery, on="student_id").sort_values("lottery_order")

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

df_result = pd.DataFrame(assignment_result)
df_result.to_csv("assignment_with_unanswered.csv", index=False)
print("✅ 未回答含む配属（1人1科1term制約付き）完了")
