import pandas as pd
from collections import defaultdict

# --- 初期配属結果の読み込み ---
# student_id と term を文字列で統一
df = pd.read_csv(
    "initial_assignment_result.csv",
    dtype={"student_id": str, "term": str}
)

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
    for i in range(1, MAX_HOPES + 1):
        dept = row.get(f"hope_{i}")
        if pd.isna(dept):
            continue
        text = str(dept).strip()
        if text == "-" or text == "":
            continue
        for term_val in student_terms[sid].values():
            hope_counts[(dept, term_val)][i] += 1

# --- 配属結果集計 ---
assigned_counts = (
    df[df["assigned_department"] != "未配属"]
      .groupby(["assigned_department", "term"])  
      .size()
      .reset_index(name="配属数")
)

# --- 希望状況の整形 ---
hope_records = []
for (dept, term), ranks in hope_counts.items():
    hope_records.append({
        "hospital_department": dept,
        "term": term,
        # 第1〜3希望の合計のみ出力
        "第1〜3希望合計": sum(ranks.get(i, 0) for i in range(1, 4))
    })
hope_df = pd.DataFrame(hope_records)

# --- 部門サマリ作成 ---
summary = pd.merge(
    hope_df,
    assigned_counts,
    how="left",
    left_on=["hospital_department", "term"],
    right_on=["assigned_department", "term"]
)
summary["配属数"] = summary["配属数"].fillna(0).astype(int)
summary = summary.drop(columns=["assigned_department"])
summary = summary.rename(columns={"hospital_department": "病院-診療科"})

# --- 不要データの除外 ---
parts = summary['病院-診療科'].str.split('-', n=1, expand=True)
mask = parts[0].str.strip().ne('') & parts[1].str.strip().ne('')
summary = summary[mask]

# --- ピボット: 第1〜3希望合計のみ, term を列に展開 (1-11) ---
# term は文字列数字なので、1から11までのリストを文字列に
terms = [str(i) for i in range(1, 12)]
pivot = summary.pivot_table(
    index='病院-診療科',
    columns='term',
    values='第1〜3希望合計',
    fill_value=0
)
# 列順を 1-11 に揃える
pivot = pivot.reindex(columns=terms, fill_value=0)
# 列名を 'Term1' 形式に変更
pivot.columns = [f"Term{c}" for c in pivot.columns]

# CSV 出力
pivot.to_csv("department_summary.csv")
print("✅ 部門サマリをピボット形式（第1〜3希望合計 Term1-Term11）で出力完了")
