import pandas as pd
import random
from collections import defaultdict

def simulate_self_flat(student_id):
    # 各種データ読み込み
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery = pd.read_csv("lottery_order.csv", dtype={'student_id': str})
    capacity = pd.read_csv("department_capacity.csv")
    terms = pd.read_csv("student_terms.csv", dtype={'student_id': str})

    # 学生のterm情報取得
    terms_row = terms[terms["student_id"] == student_id]
    if terms_row.empty:
        return {}

    term_list = [terms_row[f"term_{i}"].values[0] for i in range(1, 5)]
    response_row = responses[responses["student_id"] == student_id]
    if response_row.empty:
        return {}

    # 希望診療科リスト作成（NaNと'-'を除く）
    hopes = [response_row[f"hope_{i}"].values[0] for i in range(1, 21)
             if f"hope_{i}" in response_row.columns and
                pd.notna(response_row[f"hope_{i}"].values[0]) and
                response_row[f"hope_{i}"].values[0].strip() != "-"]
    hopes = list(dict.fromkeys(hopes))  # 重複除去

    if not hopes:
        return {}

    # 実行回数
    N = 300
    counter = {h: 0 for h in hopes}

    for _ in range(N):
        assigned = {}
        cap = {}
        for _, row in capacity.iterrows():
            dept = row["hospital_department"]
            for t in range(1, 12):
                cap[(dept, f"term_{t}")] = row[f"term_{t}"]

        for idx, term in enumerate(term_list):
            for dept in hopes:
                key = (dept, f"term_{term}")
                if cap.get(key, 0) > 0 and dept not in assigned.values():
                    cap[key] -= 1
                    assigned[f"term_{term}"] = dept
                    counter[dept] += 1
                    break
            else:
                assigned[f"term_{term}"] = "未配属"

    # 通過確率計算
    result = {dept: (count / N * 100) for dept, count in counter.items()}
    return result
