import pandas as pd
import random
import numpy as np
from collections import defaultdict
import ast

def run_simulation(responses_base: pd.DataFrame,
                   lottery_df: pd.DataFrame,
                   capacity_df: pd.DataFrame,
                   terms_df: pd.DataFrame,
                   hist_df=None) -> pd.DataFrame:
    """
    assignment simulation with imputation and multiple term preferences
    """
    # --- Setup ---
    hope_cols = [c for c in responses_base.columns if c.startswith('hope_') and not (c.endswith('_term') or c.endswith('_terms'))]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)
    term_labels = [c for c in terms_df.columns if c.startswith('term_')]

    # --- Build term_prefs: sid -> {dept: [terms]} ---
    term_prefs = {}
    for _, row in responses_base.iterrows():
        sid = row['student_id']
        dmap = {}
        for i in range(1, MAX_HOPES+1):
            dept = row.get(f'hope_{i}')
            raw = row.get(f'hope_{i}_terms')
            if pd.isna(dept) or pd.isna(raw):
                continue
            if isinstance(raw, str):
                try:
                    terms_list = ast.literal_eval(raw)
                except:
                    continue
            elif isinstance(raw, list):
                terms_list = raw
            else:
                continue
            for t in terms_list:
                if str(t).isdigit():
                    dmap.setdefault(dept, []).append(int(t))
        term_prefs[sid] = dmap

    # --- Popularity for imputation ---
    pop = defaultdict(int)
    for i in range(1, MAX_HOPES+1):
        w = MAX_HOPES + 1 - i
        for dept in responses_base.get(f'hope_{i}', pd.Series()).dropna():
            if dept and dept != '-':
                pop[dept] += w

    answered = set(responses_base['student_id'])
    all_ids  = set(terms_df['student_id'])
    unresp   = list(all_ids - answered)

    dept_list, counts = zip(*pop.items())
    weights = [c/sum(counts) for c in counts]

    generated = []
    for sid in unresp:
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

    real_df = responses_base.copy()
    real_df['is_imputed'] = False
    all_resp = pd.concat([real_df, imputed_df], ignore_index=True)

    assignment = []
    for term_label in term_labels:
        # capacities reset
        cap = {}
        for _, r in capacity_df.iterrows():
            dept = r['hospital_department']
            for t in term_labels:
                cap[(dept, t)] = int(r[t]) if not pd.isna(r[t]) else 0

        term_map = terms_df[['student_id', term_label]].rename(columns={term_label:'term'})
        term_map['term'] = term_map['term'].astype(int)
        merged = (
            all_resp
            .merge(term_map, on='student_id')
            .merge(lottery_df, on='student_id')
        )
        merged = merged.copy()
        merged['_j'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))*0.01
        merged = merged.sort_values('_j').drop(columns=['_j'])

        assigned = {}
        for _, row in merged.iterrows():
            sid  = row['student_id']
            term = row['term']
            used = assigned.get(sid, set())
            placed = False
            allowed_map = term_prefs.get(sid, {})

            for i in range(1, MAX_HOPES+1):
                dept = row.get(f'hope_{i}')
                if not dept or dept in used:
                    continue
                if dept in allowed_map and term not in allowed_map[dept]:
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
