# generate_popular_rank.py

import pandas as pd
import numpy as np

def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """
    重み付き分位数を計算します。
    values: 値の配列
    weights: 各値の重みの配列（同じ長さの配列）
    q: 0〜1 の分位点（例：0.3 なら30%点、0.5なら中央値）
    """
    # 値をソートし、それに対応する重みも並べ替え
    idx = np.argsort(values)
    sorted_vals = values[idx]
    sorted_w    = weights[idx]
    # 重みを正規化して累積和を計算
    cum_w = np.cumsum(sorted_w)
    cum_w /= cum_w[-1]
    # 累積重みが分位点以上になる最初の値を返す
    return sorted_vals[cum_w >= q][0]

def main():
    # --- 回答率と動的分位点の計算 ---
    responses    = pd.read_csv("responses.csv",    dtype=str)
    terms_df     = pd.read_csv("student_terms.csv",dtype=str)
    answered_ids = set(responses['student_id'])
    r = len(answered_ids) / len(terms_df)           # 回答率 r ∈ [0,1]
    q = r if r < 0.5 else 0.5                       # 分位点 q ∈ [0,0.5]

    # --- 割当結果と抽選順位の読み込み ---
    assign_df  = pd.read_csv("assignment_with_unanswered.csv", dtype=str)
    lottery_df = pd.read_csv("lottery_order.csv",               dtype=str)

    # lottery_order をマージ＆数値化
    assign_df['lottery_order'] = (
        assign_df['student_id']
        .map(lottery_df.set_index('student_id')['lottery_order'])
        .astype(int)
    )

    # 補完判定フラグを追加
    assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered_ids)

    # --- 科ごとに動的分位点でラインを算出 ---
    records = []
    for dept, group in assign_df.groupby('assigned_department'):
        vals    = group['lottery_order'].to_numpy()
        # 実データは重み1.0、補完データは回答率 r
        weights = np.where(group['is_imputed'], r, 1.0)
        line = weighted_quantile(vals, weights, q)
        records.append({
            'assigned_department': dept,
            '抽選順位推定ライン': line
        })

    # 結果を出力
    pop_rank = pd.DataFrame(records)
    pop_rank.to_csv("popular_departments_rank_combined.csv", index=False)
    print(f"Generated popular_departments_rank_combined.csv using q={q:.2f}")

if __name__ == '__main__':
    main()
