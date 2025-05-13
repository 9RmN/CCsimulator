# simulate_each_as_first.py
import pandas as pd
import numpy as np
import random
from collections import defaultdict

N_SIMULATIONS = 50

def compute_softmax_probs(scores: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = scores / temperature
    z = z - np.max(z)        # 数値安定化
    exp_z = np.exp(z)
    return exp_z / exp_z.sum()

def simulate_each_as_first(student_id):
    # --- データ読込 ---
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery   = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    terms     = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity  = pd.read_csv("department_capacity.csv")
    # --- 昨年実配属結果読み込み ---
    hist_df   = pd.read_csv("2024配属結果.csv", dtype=str)

    # --- 自分の希望取得 ---
    self_row = responses[responses["student_id"] == student_id]
    if self_row.empty:
        raise ValueError("student_id が responses.csv に存在しません")
    hopes = self_row.iloc[0].drop(labels="student_id").dropna().unique()
    hopes = [h for h in hopes if h not in ("", "-")]
    if not hopes:
        raise ValueError("希望が入力されていません")

    my_terms = terms[terms["student_id"] == student_id].iloc[0][
        ["term_1","term_2","term_3","term_4"]
    ].values

    lottery_row = lottery[lottery["student_id"] == student_id]
    if lottery_row.empty:
        raise ValueError("student_id が lottery_order.csv に存在しません")
    my_order = int(lottery_row["lottery_order"].iloc[0])

    others = responses[responses["student_id"] != student_id]

    # --- popularity スコア生成（回答ベース） ---
    popularity = defaultdict(int)
    MAX_HOPES = 20
    for i in range(1, MAX_HOPES+1):
        w = MAX_HOPES + 1 - i
        col = f"hope_{i}"
        if col in others.columns:
            for dept in others[col].dropna():
                if dept not in ("", "-"):
                    popularity[dept] += w

    # --- 昨年配属実績をカウント ---
    hist_count = defaultdict(int)
    for i in range(1, 12):  # term_1～term_11
        col = f"term_{i}"
        for dept in hist_df[col].dropna():
            hist_count[dept] += 1

    # --- 生スコア混合（α:β）---
    alpha, beta = 0.7, 0.3
    dept_list = list(set(popularity.keys()) | set(hist_count.keys()))
    raw_scores = np.array([
        alpha * popularity.get(d, 0) + beta * hist_count.get(d, 0)
        for d in dept_list
    ], dtype=float)

    # --- Softmax＋温度付きサンプリング準備 ---
    temperature = 3.0  # 調整可
    probs = compute_softmax_probs(raw_scores, temperature)

    # --- 未回答者リスト生成 ---
    answered_ids   = set(others["student_id"])
    all_ids        = set(terms["student_id"])
    unanswered_ids = list(all_ids - answered_ids - {student_id})

    generated_rows = []
    for uid in unanswered_ids:
        row = {"student_id": uid}
        picks = np.random.choice(dept_list, size=MAX_HOPES, replace=False, p=probs)
        for i, dept in enumerate(picks, 1):
            row[f"hope_{i}"] = dept
        generated_rows.append(row)
    generated = pd.DataFrame(generated_rows)

    # --- フルレスポンス統合 ---
    full_responses = pd.concat([others, generated], ignore_index=True)

    # --- 各希望科を第1希望にしたシミュレーション ---
    result = []
    for target in hopes:
        success = 0
        for _ in range(N_SIMULATIONS):
            # 容量リセット
            cap = {}
            for _, r in capacity.iterrows():
                dept = r["hospital_department"]
                for t in capacity.columns[1:]:
                    cap[(dept, t)] = r[t]
            # 他学生配属
            merged = full_responses.merge(terms.merge(lottery, on="student_id"), on="student_id")
            merged = merged.sort_values("lottery_order")
            stu_assigned = {}
            for _, r in merged.iterrows():
                sid = r["student_id"]
                used = stu_assigned.get(sid, set())
                for term in [r[f"term_{i}"] for i in range(1,5)]:
                    for i in range(1, MAX_HOPES+1):
                        d = r.get(f"hope_{i}", "")
                        if pd.isna(d) or d in used: continue
                        key = (d, f"term_{term}")
                        if cap.get(key, 0) > 0:
                            cap[key] -= 1
                            used.add(d)
                            stu_assigned[sid] = used
                            break
            # 自分配属判定
            for term in my_terms:
                key = (target, f"term_{term}")
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    success += 1
                    break

        pct = round(success / N_SIMULATIONS * 100, 1)
        result.append({"希望科": target, "通過確率": f"{pct}%"})

    return pd.DataFrame(result)
