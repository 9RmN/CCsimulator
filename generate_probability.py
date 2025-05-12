# generate_probability.py

import subprocess
import pandas as pd
import argparse
from collections import defaultdict

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo simulation for assignment probabilities")
    parser.add_argument('--iterations', type=int, default=5,
                        help='Number of Monte Carlo simulations (default: 5)')
    args = parser.parse_args()
    N = args.iterations

    # --- 回答率計算 ---
    responses     = pd.read_csv("responses.csv",    dtype={'student_id': str})
    terms_df      = pd.read_csv("student_terms.csv",dtype={'student_id': str})
    answered      = set(responses['student_id'])
    answered_ratio = len(answered) / len(terms_df)

    student_ids = responses['student_id'].tolist()
    hope_cols   = [c for c in responses.columns if c.startswith('hope_')]

    # カウント用
    counts        = {sid: defaultdict(float) for sid in student_ids}
    total_weights = {sid: 0.0 for sid in student_ids}

    for _ in range(N):
        # シミュレーション本体（全員分）を静かに実行
        subprocess.run(
            ['python', 'simulate_with_unanswered.py'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        assign_df = pd.read_csv("assignment_with_unanswered.csv", dtype={'student_id': str})
        assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered)

        for sid in student_ids:
            row = assign_df[assign_df['student_id'] == sid]
            if row.empty:
                continue
            assigned = row.iloc[0]['assigned_department']
            w = 1.0 if not row.iloc[0]['is_imputed'] else answered_ratio
            total_weights[sid] += w

            # マッチした希望順位にウェイトを加算
            for idx, col in enumerate(hope_cols, start=1):
                val = responses.loc[responses['student_id'] == sid, col].iloc[0]
                if pd.isna(val):
                    continue
                if val == assigned:
                    counts[sid][idx] += w
                    break

    # 確率化して CSV 出力
    rows = []
    for sid in student_ids:
        base = {'student_id': sid}
        tw = total_weights[sid] or 1.0
        for idx in range(1, len(hope_cols) + 1):
            p = counts[sid][idx] / tw * 100
            base[f'hope_{idx}_確率'] = p
        rows.append(base)

    df_prob = pd.DataFrame(rows)
    df_prob.to_csv("probability_montecarlo_combined.csv", index=False)
    print(f"Generated probability_montecarlo_combined.csv with {N} weighted simulations")

if __name__ == '__main__':
    main()
