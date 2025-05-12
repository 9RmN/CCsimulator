# generate_popular_rank.py
import pandas as pd
import numpy as np

def weighted_median(values, weights):
    # values: numpy array, weights: numpy array
    idx = np.argsort(values)
    sorted_vals = values[idx]
    sorted_w    = weights[idx]
    cumw = np.cumsum(sorted_w)
    cutoff = sorted_w.sum() / 2
    return sorted_vals[cumw >= cutoff][0]

def main():
    # 全体の回答率を算出
    responses = pd.read_csv("responses.csv", dtype=str)
    terms_df  = pd.read_csv("student_terms.csv", dtype=str)
    answered = set(responses['student_id'])
    total_students = len(terms_df)
    answered_ratio  = len(answered) / total_students

    # 割当結果と抽選順位を読み込む
    assign_df  = pd.read_csv("assignment_with_unanswered.csv", dtype=str)
    lottery_df = pd.read_csv("lottery_order.csv",                dtype=str)

    # 実データ vs 補完データ をフラグで判定
    assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered)

    # マージして weighted median を算出
    merged = assign_df.merge(lottery_df, on='student_id')
    # lottery_order を数値化
    merged['lottery_order'] = merged['lottery_order'].astype(int)

    records = []
    for dept, grp in merged.groupby('assigned_department'):
        vals = grp['lottery_order'].to_numpy()
        # 各行の重み：実回答は1.0、補完はanswered_ratio
        w = np.where(grp['is_imputed'], answered_ratio, 1.0)
        med = weighted_median(vals, w)
        records.append({
            'assigned_department': dept,
            '抽選順位中央値': med
        })

    pop_rank = pd.DataFrame(records)
    pop_rank.to_csv("popular_departments_rank_combined.csv", index=False)
    print("Generated popular_departments_rank_combined.csv with dynamic weighting")

if __name__ == '__main__':
    main()
