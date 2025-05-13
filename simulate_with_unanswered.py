import pandas as pd
import random
import numpy as np
from collections import defaultdict

def run_simulation(responses_base: pd.DataFrame,
                   lottery_df: pd.DataFrame,
                   capacity_df: pd.DataFrame,
                   terms_df: pd.DataFrame,
                   hist_df=None) -> pd.DataFrame:
    """
    Perform assignment simulation including imputed responses for non-respondents.

    :param responses_base: DataFrame with columns ['student_id', 'hope_1', ..., 'hope_N']
    :param lottery_df: DataFrame with ['student_id', 'lottery_order']
    :param capacity_df: DataFrame with ['hospital_department', 'term_1', ..., 'term_M']
    :param terms_df: DataFrame with ['student_id', 'term_1', ..., 'term_M']
    :param hist_df: (optional) DataFrame of last year's assignments, unused here
    :return: DataFrame of assignment results with columns
             ['student_id','term','assigned_department','hope_rank','is_imputed']
    """
    # Determine maximum number of hopes and term labels
    hope_cols = [c for c in responses_base.columns if c.startswith('hope_')]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)
    term_labels = [c for c in terms_df.columns if c.startswith('term_')]

    # Build popularity score from actual responses
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES + 1):
        w = MAX_HOPES + 1 - i
        col = f'hope_{i}'
        if col in responses_base:
            for dept in responses_base[col].dropna():
                if dept and dept != "-":
                    popularity[dept] += w

    # IDs for imputation
    answered_ids = set(responses_base['student_id'])
    all_ids      = set(terms_df['student_id'])
    unresp_ids   = list(all_ids - answered_ids)
    unresp_df    = lottery_df[lottery_df['student_id'].isin(unresp_ids)]

    # Prepare departments and weights for random sampling
    dept_list, counts = zip(*popularity.items())
    total = sum(counts)
    weights = [c/total for c in counts]

    # Generate imputed responses (no duplicates in each student's list)
    generated = []
    for sid in unresp_df['student_id']:
        row = {'student_id': sid}
        picks = []
        while len(picks) < MAX_HOPES:
            # weighted random draw with replacement
            choice = random.choices(dept_list, weights=weights, k=1)[0]
            if choice not in picks:
                picks.append(choice)
        for idx, dept in enumerate(picks, start=1):
            row[f'hope_{idx}'] = dept
        generated.append(row)
    imputed_df = pd.DataFrame(generated)
    imputed_df['is_imputed'] = True

    # Combine actual and imputed responses
    responses_base = responses_base.copy()
    responses_base['is_imputed'] = False
    all_responses = pd.concat([responses_base, imputed_df], ignore_index=True)

    # Perform assignment logic term by term
    assignment = []
    # Reset capacities for each simulation
    for term_label in term_labels:
        # Build capacity dict
        cap = {}
        for _, r in capacity_df.iterrows():
            dept = r['hospital_department']
            for t in term_labels:
                cap[(dept, t)] = int(r[t]) if not pd.isna(r[t]) else 0
        # Merge responses with terms and lottery, sort by lottery_order
        term_map = terms_df[['student_id', term_label]].rename(columns={term_label:'term'})
        merged = (
            all_responses
            .merge(term_map, on='student_id')
            .merge(lottery_df, on='student_id')
            .sort_values('lottery_order')
        )
        # Assign
        assigned = {}
        for _, row in merged.iterrows():
            sid = row['student_id']
            term = row['term']
            used = assigned.get(sid, set())
            placed = False
            for i in range(1, MAX_HOPES+1):
                dept = row.get(f'hope_{i}', '')
                if pd.isna(dept) or not dept or dept in used:
                    continue
                key = (dept, f'term_{term}')
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    assigned.setdefault(sid, set()).add(dept)
                    assignment.append({
                        'student_id': sid,
                        'term': term,
                        'assigned_department': dept,
                        'hope_rank': i,
                        'is_imputed': bool(row['is_imputed'])
                    })
                    placed = True
                    break
            if not placed:
                assignment.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': '未配属',
                    'hope_rank': None,
                    'is_imputed': bool(row['is_imputed'])
                })
    return pd.DataFrame(assignment)
