# generate_probability.py

import pandas as pd
import argparse
from collections import defaultdict
from simulate_with_unanswered import run_simulation  # 関数化済みと仮定

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo simulation for assignment probabilities")
    parser.add_argument('--iterations', type=int, default=5,
                        help='Number of Monte Carlo simulations')
    args = parser.parse_args()
    N = args.iterations

    # --- 一度だけ読み込む ---
    responses    = pd.read_csv("responses.csv",    dtype=str)
    lottery      = pd.read_csv("lottery_order.csv",dtype=str)
    capacity_df  = pd.read_csv("department_capacity.csv")
    terms_df     = pd.read_csv("student_terms.csv",dtype=str)

    student_ids = responses['student_id'].tolist()
    hope_cols   = [c for c in responses.columns if c.startswith('hope_')]

    counts        = {sid: defaultdict(float) for sid in student_ids}
    total_weights = {sid: 0.0 for sid in student_ids}
    answered      = set(responses['student_id'])
    answered_ratio = len(answered) / len(terms_df)

    for _ in range(N):
        assign_df = run_simulation(responses, lottery, capacity_df, terms_df)

        for sid in student_ids:
            rows = assign_df[assign_df['student_id'] == sid]
            if rows.empty:
                continue
            sub = rows.iloc[0]
            w = 1.0 if not sub['is_imputed'] else answered_ratio
            total_weights[sid] += w

            for idx, col in enumerate(hope_cols, start=1):
                val = responses.loc[responses['student_id'] == sid, col].iloc[0]
                if pd.isna(val):
                    continue
                if val == sub['assigned_department']:
                    counts[sid][idx] += w
                    break

    # 確率化して CSV 出力
    rows = []
    for sid in student_ids:
        tw = total_weights[sid] or 1.0
        base = {'student_id': sid}
        for idx in range(1, len(hope_cols) + 1):
            base[f'hope_{idx}_確率'] = counts[sid][idx] / tw * 100
        rows.append(base)

    df_prob = pd.DataFrame(rows)
    df_prob.to_csv("probability_montecarlo_combined.csv", index=False)
    print(f"Generated probability_montecarlo_combined.csv with {N} simulations")

if __name__ == '__main__':
    main()
