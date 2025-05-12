import pandas as pd
import random
from collections import defaultdict

def simulate_self_flat(student_id, num_simulations=100):
    responses_df = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery_df = pd.read_csv("lottery_order.csv", dtype={'student_id': str})
    capacity_df = pd.read_csv("department_capacity.csv")
    terms_df = pd.read_csv("student_terms.csv", dtype={'student_id': str})

    MAX_HOPES = 20
    popularity = defaultdict(int)

    for i in range(1, MAX_HOPES + 1):
        col = f"hope_{i}"
        if col in responses_df.columns:
            w = MAX_HOPES + 1 - i
            for dept in responses_df[col].dropna():
                if isinstance(dept, str) and dept.strip() and dept.strip() != "-":
                    popularity[dept.strip()] += w

    if not popularity:
        print("⚠️ popularity_score が空です。")
        return {}

    depts, weights = zip(*[(d, v / sum(popularity.values())) for d, v in popularity.items()])
    count_dict = defaultdict(int)

    for sim in range(num_simulations):
        answered_ids = set(responses_df['student_id'])
        all_ids = set(terms_df['student_id'])
        unresp_ids = list(all_ids - answered_ids)

        gen_rows = []
        for sid in unresp_ids:
            row = {"student_id": sid}
            picks = random.choices(depts, weights=weights, k=MAX_HOPES)
            for i in range(1, MAX_HOPES + 1):
                row[f"hope_{i}"] = picks[i - 1]
            gen_rows.append(row)
        gen_df = pd.DataFrame(gen_rows)

        base_df = pd.concat([responses_df, gen_df], ignore_index=True)
        base_df = base_df.copy()
        base_df['student_id'] = base_df['student_id'].astype(str)

        self_row = responses_df[responses_df["student_id"] == student_id]
        if self_row.empty:
            continue

        hopes = []
        for i in range(1, MAX_HOPES + 1):
            col = f"hope_{i}"
            if col in self_row.columns:
                val = self_row.iloc[0][col]
                if isinstance(val, str) and val.strip() and val.strip() != "-":
                    hopes.append(val.strip())
        if not hopes:
            continue

        self_terms = terms_df[terms_df["student_id"] == student_id].iloc[0]
        base_df = base_df[base_df["student_id"] != student_id]

        assignments = {}
        used = set()
        for t in range(1, 5):
            term_col = f"term_{t}"
            term_val = self_terms[term_col]
            random.shuffle(hopes)
            for dept in hopes:
                if dept in used:
                    continue
                term_key = f"term_{term_val}"
                cap_row = capacity_df[capacity_df["hospital_department"] == dept]
                if not cap_row.empty and term_key in cap_row.columns:
                    if cap_row[term_key].values[0] > 0:
                        assignments[term_key] = dept
                        used.add(dept)
                        break

        for dept in assignments.values():
            count_dict[dept] += 1

    result = {dept: round(count / num_simulations * 100, 1) for dept, count in count_dict.items()}
    return result
