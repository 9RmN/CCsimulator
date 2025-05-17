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
    Perform assignment simulation including imputed responses for non-respondents,
    with added randomness in assignment for students with the same lottery_order.
    """
    # --- Setup ---
    # only hope_n columns (exclude hope_n_term and hope_n_terms)
    hope_cols = [c for c in responses_base.columns if c.startswith('hope_') and not c.endswith('_term') and not c.endswith('_terms')]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)
    term_labels = [c for c in terms_df.columns if c.startswith('term_')]

    # --- Build term preferences from hope_i_terms columns ---
    term_prefs = {}
    for _, row in responses_base.iterrows():
        sid = row['student_id']
        prefs = []
        for i in range(1, MAX_HOPES+1):
            dept = row.get(f'hope_{i}')
            terms_list = row.get(f'hope_{i}_terms')
            if pd.notna(dept) and isinstance(terms_list, list):
                for t in terms_list:
                    try:
                        prefs.append((dept, int(t)))
                    except ValueError:
                        continue
        term_prefs[sid] = prefs

    # --- Popularity scores for imputation ---
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES+1):
        w = MAX_HOPES + 1 - i
        col = f'hope_{i}'
        for dept in responses_base.get(col, pd.Series()).dropna():
            if dept and dept != '-':
                popularity[dept] += w

    # --- Identify non-respondents ---
    answered_ids = set(responses_base['student_id'])
    all_ids      = set(terms_df['student_id'])
    unresp_ids   = list(all_ids - answered_ids)

    # --- Prepare sampling ---
    dept_list, counts = zip(*popularity.items())
    total = sum(counts)
    weights = [c/total for c in counts]

    # --- Impute hopes for non-respondents (no duplicates) ---
    generated = []
    for sid in unresp_ids:
        row = {'student_id': sid}
        picks = []
        while len(picks) < MAX_HOPES:
            choice = random.choices(dept_list, weights=weights, k=1)[0]
            if choice not in picks:
                picks.append(choice)
        for idx, dept in enumerate(picks, start=1):
            row[f'hope_{idx}'] = dept
        row['is_imputed'] = True
        generated.append(row)
    imputed_df = pd.DataFrame(generated)

    # --- Combine real and imputed ---
    real_df = responses_base.copy()
    real_df['is_imputed'] = False
    all_responses = pd.concat([real_df, imputed_df], ignore_index=True)

    # --- Assignment ---
    assignment = []
    for term_label in term_labels:
        # Reset capacities
        cap = {}
        for _, r in capacity_df.iterrows():
            dept = r['hospital_department']
            for t in term_labels:
                cap[(dept, t)] = int(r[t]) if not pd.isna(r[t]) else 0

        # Prepare merged DataFrame
        term_map = terms_df[['student_id', term_label]].rename(columns={term_label:'term'})
        merged = (
            all_responses
            .merge(term_map, on='student_id')
            .merge(lottery_df, on='student_id')
        )
        # Introduce small jitter to lottery_order
        merged = merged.copy()
        merged['_jittered_order'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))
        merged = merged.sort_values('_jittered_order').drop(columns=['_jittered_order'])

        # Allocate
        assigned = {}
        for _, row in merged.iterrows():
            sid  = row['student_id']
            term = row['term']
            used = assigned.get(sid, set())
            placed = False
            allowed = term_prefs.get(sid, [])

            for i in range(1, MAX_HOPES+1):
                dept = row.get(f'hope_{i}', '')
                if not dept or dept in used:
                    continue
                # Respect term preferences if specified
                if allowed and (dept, term) not in allowed:
                    continue
                key = (dept, f'term_{term}')
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    used.add(dept)
                    assigned[sid] = used
                    assignment.append({
                        'student_id': sid,
                        'term': term,
                        'assigned_department': dept,
                        'hope_rank': i,
                        'is_imputed': bool(row.get('is_imputed', False))
                    })
                    placed = True
                    break

            if not placed:
                assignment.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': '未配属',
                    'hope_rank': None,
                    'is_imputed': bool(row.get('is_imputed', False))
                })

    return pd.DataFrame(assignment)
