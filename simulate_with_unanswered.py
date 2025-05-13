# simulate_with_unanswered.py
import pandas as pd
import numpy as np
import random
from collections import defaultdict

def compute_softmax_probs(scores: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = scores / temperature
    z = z - np.max(z)
    exp_z = np.exp(z)
    return exp_z / exp_z.sum()

def run_simulation(responses_base: pd.DataFrame,
                   lottery_df: pd.DataFrame,
                   capacity_df: pd.DataFrame,
                   terms_df: pd.DataFrame,
                   temperature: float = 0.5) -> pd.DataFrame:
    # responses_base, lottery_df, capacity_df, terms_df は外部で読み込む

    MAX_HOPES = max(int(c.split('_')[1]) for c in responses_base.columns if c.startswith('hope_'))
    TERM_LABELS = ["term_1", "term_2", "term_3", "term_4"]

    # popularity スコア計算
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES + 1):
        w0 = MAX_HOPES + 1 - i
        col = f"hope_{i}"
        for dept in responses_base[col].dropna():
            popularity[dept] += w0

    # 未回答者抽出
    answered_ids = set(responses_base["student_id"])
    all_ids = set(terms_df["student_id"])
    unresp_ids = list(all_ids - answered_ids)
    unresp_df = lottery_df[lottery_df["student_id"].isin(unresp_ids)]

    # --- Softmax＋温度付き抽出 ---
    dept_list = list(popularity.keys())
    raw_scores = np.array([popularity[d] for d in dept_list], dtype=float)
    probs = compute_softmax_probs(raw_scores, temperature)

    generated = []
    for sid in unresp_df["student_id"]:
        row = {"student_id": sid}
        picks = np.random.choice(dept_list, size=MAX_HOPES, replace=False, p=probs)
        for idx, dept in enumerate(picks, start=1):
            row[f"hope_{idx}"] = dept
        generated.append(row)
    gen_df = pd.DataFrame(generated)
    gen_df['is_imputed'] = True

    base_df = responses_base.copy()
    base_df['is_imputed'] = False
    all_responses = pd.concat([base_df, gen_df], ignore_index=True)

    # --- 配属ロジック実行 ---
    assignment_result = []
    cap = {}
    for _, r in capacity_df.iterrows():
        dept = r["hospital_department"]
        for t in capacity_df.columns[1:]:
            cap[(dept, t)] = r[t]
    student_assigned = {}

    for term_label in TERM_LABELS:
        tm = terms_df[["student_id", term_label]].rename(columns={term_label: "term"})
        resp_term = all_responses.merge(tm, on="student_id")
        merged = resp_term.merge(lottery_df, on="student_id").sort_values("lottery_order")

        for _, r in merged.iterrows():
            sid = r["student_id"]
            term = r["term"]
            used = student_assigned.get(sid, set())
            assigned = False
            for i in range(1, MAX_HOPES + 1):
                d = r[f"hope_{i}"]
                if pd.isna(d) or d in used:
                    continue
                key = (d, f"term_{term}")
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    assignment_result.append({
                        "student_id": sid,
                        "term": term,
                        "assigned_department": d,
                        "hope_rank": i,
                        "is_imputed": r["is_imputed"]
                    })
                    used.add(d)
                    student_assigned[sid] = used
                    assigned = True
                    break
            if not assigned:
                assignment_result.append({
                    "student_id": sid,
                    "term": term,
                    "assigned_department": "未配属",
                    "hope_rank": None,
                    "is_imputed": r["is_imputed"]
                })

    return pd.DataFrame(assignment_result)
