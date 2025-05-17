import pandas as pd
import re

# --- ターム指定パース関数 ---
def parse_term_list(raw, default_terms):
    if pd.isna(raw) or not str(raw).strip():
        return None
    tokens = re.split(r"[;, \t]+", str(raw).strip())
    nums   = [int(t) for t in tokens if t.isdigit()]
    valid  = [n for n in nums if n in default_terms]
    return sorted(set(valid)) if valid else None

# --- CSV 読み込み ---
responses     = pd.read_csv("responses.csv",          dtype=str)
student_terms = pd.read_csv("student_terms.csv",      dtype=str)
capacity_df   = pd.read_csv("department_capacity.csv", dtype=str)

# --- MAX_HOPES 自動検出 ---
hope_cols = [c for c in responses.columns if c.startswith("hope_") and not c.endswith("_terms")]
MAX_HOPES = max(int(c.split("_")[1]) for c in hope_cols)

# --- student_terms_map ---
student_terms_map = {}
for _, row in student_terms.iterrows():
    sid   = row["student_id"].strip()
    terms = []
    for i in range(1,5):
        col = f"term_{i}"
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            terms.append(int(row[col]))
    student_terms_map[sid] = sorted(terms)

# --- capacities ---
capacities = {}
for _, row in capacity_df.iterrows():
    dept = row["hospital_department"]
    for col, val in row.items():
        if not col.startswith("term_"):
            continue
        term_num = int(col.split("_")[1])
        capacities.setdefault(dept, {})[term_num] = int(val) if pd.notna(val) and str(val).isdigit() else 0

# --- 配属処理 ---
assignments = []

for _, row in responses.iterrows():
    sid = row["student_id"].strip()
    if sid not in student_terms_map:
        print(f"Warning: student_id {sid} is missing → skip")
        continue

    default_terms = student_terms_map[sid]
    # この学生がすでに割り当てられた科
    used_depts = set()

    # hope_n_terms をパース
    hope_terms = {
        i: parse_term_list(row.get(f"hope_{i}_terms",""), default_terms)
        for i in range(1, MAX_HOPES+1)
    }

    # 各タームごとに
    for term in sorted(default_terms):
        assigned_dept     = None
        matched_priority = None

        for i in range(1, MAX_HOPES+1):
            dept = row.get(f"hope_{i}", "")
            if pd.isna(dept) or not dept.strip():
                continue

            # 同じ科は既に割当済みならスキップ
            if dept in used_depts:
                continue

            # 指定タームがあればその中のみ、なければ全４ターム
            term_pref = hope_terms[i]
            if term_pref is not None and term not in term_pref:
                continue

            # 空き枠チェック
            if capacities.get(dept, {}).get(term, 0) > 0:
                assigned_dept     = dept
                matched_priority = i
                capacities[dept][term] -= 1
                used_depts.add(dept)  # 一度割当た科は追加
                break

        assignments.append({
            "student_id": sid,
            "term":       term,
            "assigned_department": assigned_dept or "未配属",
            "matched_priority":   matched_priority
        })

# --- 出力 ---
pd.DataFrame(assignments).to_csv("initial_assignment_result.csv", index=False)
print("✅ 配属処理 完了")
