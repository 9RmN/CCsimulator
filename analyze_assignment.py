import pandas as pd

# 初期配属結果の読み込み
# (initial_assignment.py または simulate_with_unanswered.py の出力を使用)
df = pd.read_csv("initial_assignment_result.csv")

# 学生ごとの配属一覧を term 順に並べる
pivot_df = df.pivot(index="student_id", columns="term", values="assigned_department")
pivot_df.columns = [f"term_{int(c)}" for c in pivot_df.columns]
pivot_df.reset_index(inplace=True)

# 配属マトリクスを保存
pivot_df.to_csv("assignment_matrix.csv", index=False)

print("✅ 配属マトリクスの出力完了: assignment_matrix.csv を生成しました")
