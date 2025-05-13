# simulate_each_as_first.py
import pandas as pd
import random
from collections import defaultdict

N_SIMULATIONS = 100

def simulate_each_as_first(student_id):
    # --- データ読込 ---
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    terms = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity = pd.read_csv("department_capacity.csv")

    # 自分の希望取得
    self_row = responses[responses["student_id"] == student_id]
    if self_row.empty:
        raise ValueError("student_id が responses.csv に存在しません")
    hopes = self_row.iloc[0].drop(labels="student_id").dropna().unique()
    hopes = [h for h in hopes if h != "-" and h != ""]

    if not hopes:
        raise ValueError("希望が入力されていません")

    my_terms = terms[terms["student_id"] == student_id].iloc[0][["term_1", "term_2", "term_3", "term_4"]].values

    lottery_row = lottery[lottery["student_id"] == student_id]
    if lottery_row.empty:
        raise ValueError("student_id が lottery_order.csv に存在しません")
    my_lottery = int(lottery_row["lottery_order"].iloc[0])

    others = responses[responses["student_id"] != student_id]

    # --- popularity スコア生成（未回答者希望生成用） ---
    popularity = defaultdict(int)
    MAX_HOPES = 20
    for i in range(1, MAX_HOPES + 1):
        w = MAX_HOPES + 1 - i
        if f"hope_{i}" in others.columns:
            for dept in others[f"hope_{i}"].dropna():
                if dept != "-" and dept != "":
                    popularity[dept] += w

    answered_ids = set(others["student_id"])
    all_ids = set(terms["student_id"])
    unanswered_ids = list(all_ids - answered_ids - {student_id})
    unanswered_df = lottery[lottery["student_id"].isin(unanswered_ids)]

    depts, weights = zip(*[(d, v / sum(popularity.values())) for d, v in popularity.items()])
    generated_rows = []
    for uid in unanswered_df["student_id"]:
        row = {"student_id": uid}
        picks = random.choices(depts, weights=weights, k=MAX_HOPES)
        for i, dept in enumerate(picks, 1):
            row[f"hope_{i}"] = dept
        generated_rows.append(row)
    generated = pd.DataFrame(generated_rows)

    # ベース responses 統合
    full_responses = pd.concat([others, generated], ignore_index=True)

    # --- 各希望科を第1希望にしたシミュレーション ---
    result = []

    for target_dept in hopes:
        success_count = 0

        for _ in range(N_SIMULATIONS):
            # 容量初期化
            cap = {}
            for _, r in capacity.iterrows():
                dept = r["hospital_department"]
                for t in capacity.columns[1:]:
                    cap[(dept, t)] = r[t]

            # 他の学生の割り当て
            all_terms = terms.merge(lottery, on="student_id")
            merged = full_responses.merge(all_terms, on="student_id")
            merged = merged.sort_values("lottery_order")
            student_assigned = {}

            for _, r in merged.iterrows():
                sid = r["student_id"]
                term_list = [r[f"term_{i}"] for i in range(1, 5)]
                used = student_assigned.get(sid, set())
                for term in term_list:
                    for i in range(1, MAX_HOPES + 1):
                        d = r.get(f"hope_{i}", "")
                        if pd.isna(d) or d in used:
                            continue
                        key = (d, f"term_{term}")
                        if cap.get(key, 0) > 0:
                            cap[key] -= 1
                            used.add(d)
                            student_assigned[sid] = used
                            break

            # 自分が target_dept を第1希望として提出したと仮定して割り当て
            for term in my_terms:
                key = (target_dept, f"term_{term}")
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    success_count += 1
                    break

        percent = round(success_count / N_SIMULATIONS * 100, 1)
        result.append({
            "希望科": target_dept,
            "通過確率（仮に第1希望として出した場合）": f"{percent}%"
        })

    return pd.DataFrame(result)
