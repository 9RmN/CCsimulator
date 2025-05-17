import pandas as pd
import re

# --- ユーティリティ関数 ---
def parse_term_list(raw, default_terms):
    """
    raw: CSV の hope_n_terms フィールド（例: "2,5" / "3;7" / "" / NaN）
    default_terms: student_terms_map[sid] で取得した、その学生の基本４タームリスト
    戻り値: 指定タームのリスト（昇順）, 指定なしの場合は None
    """
    if pd.isna(raw) or not str(raw).strip():
        return None
    # 「,」「;」「 」などで分割
    tokens = re.split(r"[;, \t]+", str(raw).strip())
    # 数字だけ抽出
    terms = [int(t) for t in tokens if t.isdigit()]
    # default_terms のサブセットのみ残す
    valid = [t for t in terms if t in default_terms]
    if not valid:
        return None
    return sorted(set(valid))

# --- データ読み込み ---
responses = pd.read_csv("responses.csv", dtype=str)  # student_id, hope_1_department, hope_1_terms, ..., hope_10_
student_terms_df = pd.read_csv("student_terms.csv", dtype={"student_id": str})
capacity_df = pd.read_csv("department_capacity.csv", dtype={"department": str, "term": int, "capacity": int})

# student_terms_map: { student_id: [t1,t2,t3,t4] }
student_terms_map = {
    row["student_id"]: list(map(int, row["terms"].split(",")))
    for _, row in student_terms_df.iterrows()
}

# capacities: { dept: { term: capacity_int } }
capacities = {}
for _, row in capacity_df.iterrows():
    dept = row["department"]
    term = row["term"]
    cap  = int(row["capacity"])
    capacities.setdefault(dept, {})[term] = cap

# --- 割当処理 ---
assignments = []  # 出力用リスト

for _, row in responses.iterrows():
    sid = row["student_id"]
    default_terms = student_terms_map[sid]

    # 各優先度のターム指定をパース
    hope_terms = {
        i: parse_term_list(row.get(f"hope_{i}_terms", None), default_terms)
        for i in range(1, 11)
    }

    # この学生の割当結果
    for term in sorted(default_terms):
        assigned_dept = None
        for i in range(1, 11):
            dept = row.get(f"hope_{i}_department", "")
            if pd.isna(dept) or not dept:
                continue

            term_pref = hope_terms[i]
            # 指定タームがあり & 今回の term が指定外ならスキップ
            if term_pref is not None and term not in term_pref:
                continue

            # 空き枠チェック
            if capacities.get(dept, {}).get(term, 0) > 0:
                assigned_dept = dept
                capacities[dept][term] -= 1
                break

        # 割当結果を記録
        assignments.append({
            "student_id": sid,
            "term": term,
            "assigned_department": assigned_dept or "未配属",
            "matched_priority": i if assigned_dept else None
        })

# DataFrame にまとめて CSV 出力
assign_df = pd.DataFrame(assignments)
assign_df.to_csv("initial_assignment_result.csv", index=False)
print("initial_assignment.py: 割当処理 完了")
