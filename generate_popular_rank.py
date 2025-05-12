# generate_popular_rank.py

import pandas as pd
import numpy as np

def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """
    重み付き中央値を計算する関数。
    values: 値の配列
    weights: 各値の重みの配列
    """
    # 値をソートし、それに対応する重みも並べ替え
    idx = np.argsort(values)
    sorted_vals = values[idx]
    sorted_w    = weights[idx]
    cum_w       = np.cumsum(sorted_w)
    cutoff      = sorted_w.sum() / 2
    # 累積重みが総重みの半分を超える最初の値を中央値とする
    return sorted_vals[cum_w >= cutoff][0]

def main():
    # --- 回答率計算（補完データの重み w_impute = 回答率） ---
    responses    = pd.read_csv("responses.csv",    dtype=str)
    terms_df     = pd.read_csv("student_terms.csv",dtype=str)
    answered_ids = set(responses['student_id'])
    answered_ratio = len(answered_ids) / len(terms_df)

    # --- 割当結果と抽選順位の読み込み ---
    assign_df  = pd.read_csv("assignment_with_unanswered.csv", dtype=str)
    lottery_df = pd.read_csv("lottery_order.csv",               dtype=str)

    # lottery_order を結合＆数値化
    assign_df['lottery_order'] = (
        assign_df['student_id']
        .map(lottery_df.set_index('student_id')['lottery_order'])
        .astype(int)
    )

    # 補完判定フラグを追加
    assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered_ids)

    # --- 部門ごとに重み付き中央値を計算 ---
    records = []
    for dept, group in assign_df.groupby('assigned_department'):
        vals = group['lottery_order'].to_numpy()
        # 重み：実データは1.0、補完データは回答率
        weights = np.where(group['is_imputed'], answered_ratio, 1.0)
        med = weighted_median(vals, weights)
        records.append({
            'assigned_department': dept,
            '抽選順位中央値': med
        })

    # 結果を DataFrame にまとめて出力
    pop_rank = pd.DataFrame(records)
    pop_rank.to_csv("popular_departments_rank_combined.csv", index=False)
    print("Generated popular_departments_rank_combined.csv with dynamic weighting")

if __name__ == '__main__':
    main()
