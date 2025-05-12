# generate_popular_rank.py

import pandas as pd
import numpy as np

def weighted_median(values, weights):
    idx = np.argsort(values)
    vs = values[idx]
    ws = weights[idx]
    cumw = np.cumsum(ws)
    cutoff = ws.sum() / 2
    return vs[cumw >= cutoff][0]

def main():
    # --- 回答率計算 ---
    responses     = pd.read_csv("responses.csv",    dtype=str)
    terms_df      = pd.read_csv("student_terms.csv",dtype=str)
    answered      = set(responses['student_id'])
    answered_ratio = len(answered) / len(terms_df)

    # --- 割当結果と抽選順位読み込み ---
    assign_df    = pd.read_csv("assignment_with_unanswered.csv", dtype=str)
    lottery_df   = pd.read_csv("lottery_order.csv",               dtype=str)
    # lottery_order をマージ＆数値化
    assign_df['lottery_order'] = assign_df['student_id']\
        .map(lottery_df.set_index('student_id')['lottery_order'])\
        .astype(int)
    # 補完判定フラグ
    assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered)

    # --- 部門ごとに weighted median を計算 ---
    records = []
    for dept, grp in assign_df.groupby('assigned_department'):
        vals = grp['lottery_order'].to_numpy()
        ws   = np.where(grp['is_imputed'], answered_ratio, 1.0)
        med  = weighted_median(vals, ws)
        records.append({
            'assigned_department': dept,
            '抽選順位中央値': med
        })

    pop_rank = pd.DataFrame(records)
    pop_rank.to_csv("popular_departments_rank_combined.csv", index=False)
    print("Generated popular_departments_rank_combined.csv with dynamic weighting")

if __name__ == '__main__':
    main()
