import pandas as pd
import re

# --- 1. ターム指定パース関数 ---
def parse_term_list(raw, default_terms):
    """
    raw: responses.csv の hope_n_terms フィールド
    default_terms: その学生の基本４タームリスト
    戻り値: 指定タームのリスト（昇順）、指定なし／不正入力時は None
    """
    if pd.isna(raw) or not str(raw).strip():
        return None
    tokens = re.split(r"[;, \t]+", str(raw).strip())
    terms = [int(t) for t in tokens if t.isdigit()]
    # default_terms のサブセットのみ残す
    valid = [t for t in terms if t in default_terms]
    if not valid:
        return None
    return sorted(set(valid))

# --- データ読み込み ---
responses = pd.read_csv("responses.csv", dtype=str)

student_terms_df = pd.read_csv("student_terms.csv", dtype=str)
# student_terms.csv に term_1～term_4 列がある前提でマップ作成
student_terms_map = {
    row["student_id"]: [
        int(row["term_1"]),
        int(row["term_2"]),
        int(row["term_3"]),
        int(row["term_4"])
    ]
    for _, row in student_terms_df.iterrows()
}

capacity_df = pd.read_csv("department_capacity.csv", dtype={"department": str, "term": int, "capacity": int})
# capacities: { dept: { term: capacity_int } }
capacities = {}
for _, row in capacity_df.iterrows():
    dept = row["department"]
    term = int(row["term"])
    cap  = int(row["capacity"])
    capacities.setdefault(dept, {})[term] = cap

# --- 配属処理 ---
assignments = []

for _, row in responses.iterrows():
    sid = row["student_id"]
    default_terms = student_terms_map[sid]

    # 各優先度のターム指定をパース（1～10）
    hope_terms = {
        i: parse_term_list(row.get(f"hope_{i}_terms", None), default_terms)
        for i in range(1, 11)
    }

    # 各タームごとに割り当て
    for term in sorted(default_terms):
        assigned_dept = None
        matched_priority = None

        for i in range(1, 11):
            dept = row.get(f"hope_{i}_department", "")
            if pd.isna(dept) or not dept:
                continue

            term_pref = hope_terms[i]
            # 2. 指定タームがあり、かつこの term が指定外ならスキップ
            if term_pref is not None and term not in term_pref:
                continue

            # 空き枠があれば割当
            if capacities.get(dept, {}).get(term, 0) > 0:
                assigned_dept = dept
                matched_priority = i
                capacities[dept][term] -= 1
                break

        assignments.append({
            "student_id": sid,
            "term": term,
            "assigned_department": assigned_dept or "未配属",
            "matched_priority": matched_priority
        })

# 結果を DataFrame にまとめて CSV 出力
assign_df = pd.DataFrame(assignments)
assign_df.to_csv("initial_assignment_result.csv", index=False)
print("initial_assignment.py: 割当処理 完了")
