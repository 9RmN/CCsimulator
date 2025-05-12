# generate_probability.py
import subprocess
import pandas as pd
import argparse
from collections import defaultdict

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo simulation for assignment probabilities")
    parser.add_argument('--iterations', type=int, default=20,
                        help='Number of Monte Carlo simulations')
    args = parser.parse_args()
    N = args.iterations

    # 回答率を算出（重み付け割合に使用）
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    terms_df  = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    answered = set(responses['student_id'])
    answered_ratio = len(answered) / len(terms_df)

    # student_ids と希望列
    student_ids = responses['student_id'].tolist()
    hope_cols = [c for c in responses.columns if c.startswith('hope_')]

    # カウント用辞書
    counts = {sid: defaultdict(float) for sid in student_ids}
    total_weights = {sid: 0.0 for sid in student_ids}

    for _ in range(N):
        subprocess.run(['python', 'simulate_with_unanswered.py'], check=True)
        assign_df = pd.read_csv("assignment_with_unanswered.csv", dtype={'student_id': str})

        # is_imputed 判定
        assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered)

        for sid in student_ids:
            row = assign_df[assign_df['student_id'] == sid]
            if row.empty:
                continue
            assigned = row.iloc[0]['assigned_department']
            weight = 1.0 if not row.iloc[0]['is_imputed'] else answered_ratio
            total_weights[sid] += weight

            # マッチした希望順位に重みを加算
            for idx, col in enumerate(hope_cols, start=1):
                hope_val = responses.loc[responses['student_id'] == sid, col].iloc[0]
                if pd.isna(hope_val):
                    continue
                if hope_val == assigned:
                    counts[sid][idx] += weight
                    break

    # 確率化して CSV 出力
    rows = []
    for sid in student_ids:
        base = {'student_id': sid}
        for idx in range(1, len(hope_cols) + 1):
            p = counts[sid][idx] / total_weights[sid] * 100 if total_weights[sid] > 0 else 0
            base[f'hope_{idx}_確率'] = p
        rows.append(base)

    df_prob = pd.DataFrame(rows)
    df_prob.to_csv("probability_montecarlo_combined.csv", index=False)
    print(f"Generated probability_montecarlo_combined.csv with {N} weighted simulations")

if __name__ == '__main__':
    main()
