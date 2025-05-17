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
    valid = [t for t in terms if t in default_terms]
    if not valid:
        return None
    return sorted(set(valid))


# --- データ読み込み ---
responses       = pd.read_csv("responses.csv",        dtype=str)
student_terms_df = pd.read_csv("student_terms.csv",    dtype=str)
capacity_df     = pd.read_csv("department_capacity.csv", dtype={"department": str, "term": int, "capacity": int})

# --- 2. student_terms_map の構築 ---
# student_terms.csv に term_1～term_4 の各列がある前提
student_terms_map = {}
for _, row in student_terms_df.iterrows():
    sid = str(row["student_id"]).strip()
    # term_1～term_4 をリスト化
    terms = []
    for i in range(1, 5):
        col = f"term_{i}"
        if col in row and pd.notna(row[col]):
            terms.append(int(row[col]))
    student_terms_map[sid] = sorted(terms)


# --- 3. capacities 辞書化 ---
# { department: { term: capacity_int, ... }, ... }
capacities = {}
for _, row in capacity_df.iterrows():
    dept = row["department"]
    term = int(row["term"])
    cap  = int(row["capacity"])
    capacities.setdefault(dept, {})[term] = cap


# --- 初期配属処理 ---
assignments = []

for _, row in responses.iterrows():
    sid = str(row["student_id"]).strip()
    # student_terms.csv にない ID はスキップ
    if sid not in student_terms_map:
        print(f"Warning: student_id {sid} not found in student_terms.csv → スキップ")
        continue

    default_terms = student_terms_map[sid]

    # 1～10 の希望タームをパース
    hope_terms = {
        i: parse_term_list(row.get(f"hope_{i}_terms", ""), default_terms)
        for i in range(1, 11)
    }

    # 各 default_term（4つ）ごとに割当試行
    for term in sorted(default_terms):
        assigned_dept     = None
        matched_priority = None

        for i in range(1, 11):
            dept = row.get(f"hope_{i}_department", "")
            if pd.isna(dept) or not dept.strip():
                continue

            term_pref = hope_terms[i]
            # 指定タームあり ＆ 今の term が指定外 → スキップ
            if term_pref is not None and term not in term_pref:
                continue

            # 空き枠があれば割当
            if capacities.get(dept, {}).get(term, 0) > 0:
                assigned_dept     = dept
                matched_priority = i
                capacities[dept][term] -= 1
                break

        assignments.append({
            "student_id": sid,
            "term": term,
            "assigned_department": assigned_dept or "未配属",
            "matched_priority": matched_priority
        })


# 結果を CSV 出力
assign_df = pd.DataFrame(assignments)
assign_df.to_csv("initial_assignment_result.csv", index=False)
print("initial_assignment.py: 割当処理 完了")
