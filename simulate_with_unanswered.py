# generate_probability.py
import subprocess
import pandas as pd
import argparse
from collections import defaultdict

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo simulation for assignment probabilities")
    parser.add_argument('--iterations', type=int, default=20,
                        help='Number of Monte Carlo simulations (default: 20)')
    args = parser.parse_args()
    N = args.iterations

    # 読み込み
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    student_ids = responses['student_id'].tolist()
    hope_cols = [col for col in responses.columns if col.startswith('hope_')]

    # カウント用辞書
    counts = {sid: defaultdict(int) for sid in student_ids}

    for i in range(N):
        # 未回答含めた配属シミュレーションを実行（is_imputed フラグは不要）
        subprocess.run(['python', 'simulate_with_unanswered.py'], check=True)
        assign_df = pd.read_csv("assignment_with_unanswered.csv", dtype={'student_id': str})

        for sid in student_ids:
            row = assign_df[assign_df['student_id'] == sid]
            if row.empty:
                continue
            assigned_dept = row.iloc[0]['assigned_department']
            # 希望順位を判定
            for idx, hope_col in enumerate(hope_cols, start=1):
                hope_val = responses.loc[responses['student_id'] == sid, hope_col].iloc[0]
                if pd.isna(hope_val):
                    continue
                if hope_val == assigned_dept:
                    counts[sid][idx] += 1
                    break

    # 確率化して DataFrame 化
    rows = []
    for sid in student_ids:
        row = {'student_id': sid}
        for idx in range(1, len(hope_cols) + 1):
            prob = counts[sid][idx] / N * 100
            row[f'hope_{idx}_確率'] = prob
        rows.append(row)

    df_prob = pd.DataFrame(rows)
    df_prob.to_csv("probability_montecarlo_combined.csv", index=False)
    print(f"Generated probability_montecarlo_combined.csv with {N} simulations")

if __name__ == '__main__':
    main()
