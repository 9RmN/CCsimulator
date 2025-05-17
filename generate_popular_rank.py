#!/usr/bin/env python3
import pandas as pd
import numpy as np

def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """
    重み付き分位数を計算します。
    values: 値の配列
    weights: 各値の重みの配列（同じ長さの配列）
    q: 0〜1 の分位点（例：0.3 なら30%点、0.5なら中央値）
    """
    idx = np.argsort(values)
    sorted_vals = values[idx]
    sorted_w    = weights[idx]
    cum_w = np.cumsum(sorted_w)
    cum_w /= cum_w[-1]
    return float(sorted_vals[cum_w >= q][0])


def main():
    # --- データ読み込み ---
    # 回答率計算用
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    terms_df  = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    answered_ids = set(responses['student_id'])
    r = len(answered_ids) / len(terms_df)

    # 割当結果＋抽選順序
    assign_df  = pd.read_csv("assignment_with_unanswered.csv", dtype={'student_id': str, 'term': int, 'assigned_department': str})
    lottery_df = pd.read_csv("lottery_order.csv",                 dtype={'student_id': str, 'lottery_order': int})
    assign_df['lottery_order'] = assign_df['student_id'].map(lottery_df.set_index('student_id')['lottery_order'])
    assign_df['is_imputed'] = ~assign_df['student_id'].isin(answered_ids)

    # capacity lookup: (department, term) -> slots
    cap_df = pd.read_csv("department_capacity.csv")
    capacity = {}
    for _, row in cap_df.iterrows():
        dept = row['hospital_department']
        for col in cap_df.columns:
            if col.startswith('term_'):
                term = int(col.split('_')[1])
                slots = int(row[col] if not pd.isna(row[col]) else 0)
                capacity[(dept, term)] = slots

    records = []
    # 部門×タームで分位数計算
    grouped = assign_df.groupby(['assigned_department', 'term'], as_index=False)
    for (dept, term), group in grouped:
        vals = group['lottery_order'].astype(int).to_numpy()
        weights = np.where(group['is_imputed'], r, 1.0)
        applicants = len(group)
        slots = capacity.get((dept, term), 0)
        # 分位点を定員/応募者数に合わせて動的に決定 (0〜1 に制限)
        q_dept = min(max(slots / applicants if applicants > 0 else 0, 0), 1)
        cutoff = weighted_quantile(vals, weights, q_dept)
        records.append({
            'assigned_department': dept,
            'term': term,
            '抽選順位推定ライン': cutoff,
            '分位点': q_dept
        })

    # 結果保存
    pop_term_rank = pd.DataFrame(records)
    pop_term_rank.to_csv("popular_departments_rank_by_term.csv", index=False)
    print(f"Generated popular_departments_rank_by_term.csv with dynamic quantiles and term breakdown (r={r:.2f})")

if __name__ == '__main__':
    main()
