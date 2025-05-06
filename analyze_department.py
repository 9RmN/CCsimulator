
import pandas as pd
from collections import defaultdict

# 初期配属結果の読み込み
df = pd.read_csv("initial_assignment_result.csv")

# responses の読み込み（希望情報）
responses = pd.read_csv("responses.csv")
terms_df = pd.read_csv("student_terms.csv")
hope_columns = [col for col in responses.columns if col.startswith("hope_")]
MAX_HOPES = max([int(col.split("_")[1]) for col in hope_columns])

# 各学生について、各 term ごとに希望診療科を集計
student_terms = terms_df.set_index("student_id").to_dict(orient="index")
hope_counts = defaultdict(lambda: defaultdict(int))  # dept -> term -> count

for _, row in responses.iterrows():
    sid = row["student_id"]
    if sid not in student_terms:
        continue
    for i in range(1, MAX_HOPES + 1):
        dept = row.get(f"hope_{i}")
        if pd.isna(dept):
            continue
        for term_label, term_val in student_terms[sid].items():
            key = (dept, term_val)
            hope_counts[key][i] += 1

# 配属状況の集計
assigned_counts = df[df["assigned_department"] != "未配属"].groupby(
    ["assigned_department", "term"]
).size().reset_index(name="配属数")

# 希望状況の整形
hope_records = []
for (dept, term), rank_dict in hope_counts.items():
    total_hopes = sum(rank_dict.values())
    top_3 = sum(rank_dict.get(i, 0) for i in range(1, 4))
    hope_records.append({
        "病院-診療科": dept,
        "term": term,
        "希望者数": total_hopes,
        "うち第1〜3希望": top_3,
        "第1希望数": rank_dict.get(1, 0),
        "第2希望数": rank_dict.get(2, 0),
        "第3希望数": rank_dict.get(3, 0)
    })

hope_df = pd.DataFrame(hope_records)

# マージして出力
summary = pd.merge(hope_df, assigned_counts, how="left",
                   left_on=["病院-診療科", "term"],
                   right_on=["assigned_department", "term"])
summary = summary.drop(columns=["assigned_department"])
summary["配属数"] = summary["配属数"].fillna(0).astype(int)

summary.to_csv("department_summary.csv", index=False)
print("✅ 診療科ごとの希望・配属状況まとめ完了")
