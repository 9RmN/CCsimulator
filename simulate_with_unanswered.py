# simulate_with_unanswered.py
import pandas as pd
import numpy as np
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
                   hist_df: pd.DataFrame,
                   temperature: float = 3.0,
                   alpha: float = 0.7,
                   beta: float = 0.3) -> pd.DataFrame:
    # --- popularity スコア計算（回答ベース）---
    MAX_HOPES = max(int(c.split('_')[1]) for c in responses_base.columns if c.startswith('hope_'))
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES+1):
        w = MAX_HOPES + 1 - i
        for dept in responses_base[f"hope_{i}"].dropna():
            popularity[dept] += w

    # --- 昨年実配属実績カウント ---
    hist_count = defaultdict(int)
    for i in range(1, 12):
        for dept in hist_df[f"term_{i}"].dropna():
            hist_count[dept] += 1

    # --- 生スコア混合 ---
    dept_list = list(set(popularity.keys()) | set(hist_count.keys()))
    raw_scores = np.array([
        alpha * popularity.get(d, 0) + beta * hist_count.get(d, 0)
        for d in dept_list
    ], dtype=float)

    # --- Softmax＋温度付き確率分布 ---
    probs = compute_softmax_probs(raw_scores, temperature)

    # --- 未回答者の希望リスト生成 ---
    answered = set(responses_base["student_id"])
    all_ids  = set(terms_df["student_id"])
    unresp   = list(all_ids - answered)
    gen_rows = []
    for sid in unresp:
        row = {"student_id": sid}
        picks = np.random.choice(dept_list, size=MAX_HOPES, replace=False, p=probs)
        for i, dept in enumerate(picks, 1):
            row[f"hope_{i}"] = dept
        gen_rows.append(row)
    gen_df = pd.DataFrame(gen_rows)
    gen_df['is_imputed'] = True

    # --- full responses 結合 ---
    base_df = responses_base.copy()
    base_df['is_imputed'] = False
    all_resp = pd.concat([base_df, gen_df], ignore_index=True)

    # --- 配属ロジック ---
    result = []
    cap = {}
    for _, r in capacity_df.iterrows():
        dept = r["hospital_department"]
        for col in capacity_df.columns[1:]:
            cap[(dept, col)] = r[col]
    assigned = {}

    for term_label in ["term_1","term_2","term_3","term_4"]:
        tm = terms_df[["student_id", term_label]].rename(columns={term_label:"term"})
        merged = all_resp.merge(tm, on="student_id").merge(lottery_df, on="student_id")
        merged = merged.sort_values("lottery_order")
        for _, r in merged.iterrows():
            sid = r["student_id"]
            used = assigned.get(sid, set())
            placed = False
            for i in range(1, MAX_HOPES+1):
                d = r[f"hope_{i}"]
                if pd.isna(d) or d in used: continue
                key = (d, f"term_{r['term']}")
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    used.add(d)
                    assigned[sid] = used
                    result.append({
                        "student_id": sid,
                        "term": r["term"],
                        "assigned_department": d,
                        "hope_rank": i,
                        "is_imputed": r["is_imputed"]
                    })
                    placed = True
                    break
            if not placed:
                result.append({
                    "student_id": sid,
                    "term": r["term"],
                    "assigned_department": "未配属",
                    "hope_rank": None,
                    "is_imputed": r["is_imputed"]
                })

    return pd.DataFrame(result)
