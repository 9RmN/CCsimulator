#!/usr/bin/env python3
import pandas as pd
import argparse
from collections import defaultdict
from simulate_with_unanswered import run_simulation  # 関数化済みと仮定

def main():
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulation for assignment probabilities"
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of Monte Carlo simulations (default: 100)'
    )
    args = parser.parse_args()
    N = args.iterations

    # --- 一度だけデータ読み込み ---
    responses   = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery     = pd.read_csv("lottery_order.csv", dtype={'student_id': str})
    capacity_df = pd.read_csv("department_capacity.csv")
    terms_df    = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    # 追加：昨年配属結果を読み込む（将来利用）
    hist_df     = pd.read_csv("2024配属結果.csv", dtype={'student_id': str})

    student_ids = responses['student_id'].tolist()
    hope_cols   = [c for c in responses.columns if c.startswith('hope_')]

    # 重みとカウント用の辞書
    counts        = {sid: defaultdict(float) for sid in student_ids}
    total_weights = {sid: 0.0 for sid in student_ids}

    # 回答済/未回答者の判別
    answered       = set(responses['student_id'])
    answered_ratio = len(answered) / len(terms_df)

    # モンテカルロシミュレーション
    for _ in range(N):
        assign_df = run_simulation(
            responses,
            lottery,
            capacity_df,
            terms_df,
            hist_df  # 追加引数
        )
        # 各行に is_imputed フラグをセット
        assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered)

        for sid in student_ids:
            # 当該学生の全ターム配属結果
            rows = assign_df[assign_df['student_id'] == sid]
            if rows.empty:
                continue
            # 重み: 回答済は1.0、未回答は回答率
            w = 1.0 if sid in answered else answered_ratio
            total_weights[sid] += w

            # 全タームで配属された科の集合（未配属は除外）
            assigned_depts = set(rows['assigned_department']) - {None, '未配属'}

            # 各希望順位ごとに、最初にマッチした科だけをカウント
            for idx, col in enumerate(hope_cols, start=1):
                val = responses.loc[responses['student_id'] == sid, col].iloc[0]
                if pd.isna(val):
                    continue
                if val in assigned_depts:
                    counts[sid][idx] += w
                    # 最初にマッチした希望のみカウント
                    break

    # スムージング (ベイズ補正) を入れて確率化
    K = 2.0  # スムージングパラメータ
    output_rows = []
    for sid in student_ids:
        tw = total_weights[sid] or 1.0
        base = {'student_id': sid}
        for idx in range(1, len(hope_cols) + 1):
            num = counts[sid][idx]
            # (成功シミュレーション回数 + 1) / (重み合計 + K) * 100%
            p = (num + 1.0) / (tw + K) * 100.0
            base[f'hope_{idx}_確率'] = p
        output_rows.append(base)

    df_prob = pd.DataFrame(output_rows)
    df_prob.to_csv(
        "probability_montecarlo_combined.csv", index=False
    )
    print(
        f"Generated probability_montecarlo_combined.csv with {N} simulations and Bayesian smoothing (K={K})"
    )

if __name__ == '__main__':
    main()
