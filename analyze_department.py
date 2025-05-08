import pandas as pd
from collections import defaultdict

# --- 初期配属結果の読み込み ---
# student_id と term を文字列で統一
df = pd.read_csv("initial_assignment_result.csv", dtype={"student_id": str, "term": str})

# --- responses と student_terms の読み込み ---
responses = pd.read_csv("responses.csv", dtype=str)
terms_df  = pd.read_csv("student_terms.csv", dtype=str)
# 最大希望数の検出
hope_columns = [col for col in responses.columns if col.startswith("hope_")]
MAX_HOPES   = max(int(col.split("_")[1]) for col in hope_columns)

# --- 希望データ集計 ---
student_terms = terms_df.set_index("student_id").to_dict(orient="index")
hope_counts = defaultdict(lambda: defaultdict(int))  # (dept, term) -> rank counts

for _, row in responses.iterrows():
    sid = str(row["student_id"]).lstrip('0')
    if sid not in student_terms:
        continue
    # student_terms[sid] は {"term_1": "1", ...}
    for i in range(1, MAX_HOPES + 1):
        dept = row.get(f"hope_{i}")
        if pd.isna(dept):
            continue
        # 各 term に対してカウント
        for term_val in student_terms[sid].values():
            # term_val は文字列
            hope_counts[(dept, term_val)][i] += 1

# --- 配属結果集計 ---
# df['term'] は文字列として読み込み済み
assigned_counts = (
    df[df["assigned_department"] != "未配属"]
      .groupby(["assigned_department", "term"])  
      .size()
      .reset_index(name="配属数")
)
# ここで term は文字列

# --- 希望状況の整形 ---
hope_records = []
for (dept, term), ranks in hope_counts.items():
    total_hopes = sum(ranks.values())
    top_3       = sum(ranks.get(i, 0) for i in range(1, 4))
    hope_records.append({
        "hospital_department": dept,
        "term": term,  # 文字列
        "希望者数": total_hopes,
        "うち第1〜3希望": top_3,
        "第1希望数": ranks.get(1, 0),
        "第2希望数": ranks.get(2, 0),
        "第3希望数": ranks.get(3, 0)
    })
hope_df = pd.DataFrame(hope_records)

# --- 部門サマリ作成 ---
summary = pd.merge(
    hope_df,
    assigned_counts,
    how="left",
    left_on=["hospital_department", "term"],
    right_on=["assigned_department",   "term"]
)
summary["配属数"] = summary["配属数"].fillna(0).astype(int)
summary = summary.drop(columns=["assigned_department"])
# 日本語列名へ
summary = summary.rename(columns={"hospital_department": "病院-診療科"})

# CSV 出力
summary.to_csv("department_summary.csv", index=False)
print("✅ 診療科ごとの希望・配属状況まとめ完了")
