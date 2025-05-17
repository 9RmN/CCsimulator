import pandas as pd
import random
import numpy as np
from collections import defaultdict
import ast

# --- データ読み込み ---
responses   = pd.read_csv("responses.csv", dtype=str)
lottery     = pd.read_csv("lottery_order.csv", dtype={"student_id":str, "lottery_order":int})
capacity_df = pd.read_csv("department_capacity.csv")
terms_df    = pd.read_csv("student_terms.csv", dtype=str)

# student_id の正規化
responses['student_id'] = responses['student_id'].str.lstrip('0')
lottery['student_id']   = lottery['student_id'].str.lstrip('0')
terms_df['student_id']  = terms_df['student_id'].str.lstrip('0')

# hope_n 列のみを特定
hope_cols = [c for c in responses.columns if c.startswith('hope_') and not (c.endswith('_term') or c.endswith('_terms'))]
MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)
# term 列ラベル
term_labels = [c for c in terms_df.columns if c.startswith('term_')]

# --- Build term_prefs: sid -> {dept: [terms]} ---
term_prefs = {}
for _, row in responses.iterrows():
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

# --- Build student_terms_map: sid -> [all terms] ---
student_terms_map = {}
for _, row in terms_df.iterrows():
    sid = row['student_id']
    terms = []
    for col in term_labels:
        val = row.get(col)
        if pd.notna(val) and str(val).isdigit():
            terms.append(int(val))
    student_terms_map[sid] = terms

# --- Popularity for imputation ---
popularity = defaultdict(int)
for i in range(1, MAX_HOPES+1):
    w = MAX_HOPES + 1 - i
    for dept in responses.get(f'hope_{i}', pd.Series()).dropna():
        if dept and dept != '-':
            popularity[dept] += w

answered_ids = set(responses['student_id'])
all_ids      = set(terms_df['student_id'])
unresp_ids   = list(all_ids - answered_ids)

dept_list, counts = zip(*popularity.items())
weights = [c/sum(counts) for c in counts]

# Impute hopes for non-respondents
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

# Combine real and imputed
eal_df = responses.copy()
real_df['is_imputed'] = False
all_resp = pd.concat([real_df, imputed_df], ignore_index=True)

# Assignment simulation
def run_simulation(responses_base, lottery_df, capacity_df, terms_df, hist_df=None):
    assignment = []
    for term_label in term_labels:
        # Reset capacities
        cap = {}
        for _, r in capacity_df.iterrows():
            dept = r['hospital_department']
            for tcol in term_labels:
                cap[(dept, tcol)] = int(r[tcol]) if not pd.isna(r[tcol]) else 0

        # Merge data
        term_map = terms_df[['student_id', term_label]].rename(columns={term_label:'term'})
        term_map['term'] = term_map['term'].astype(int)
        merged = (
            all_resp
            .merge(term_map, on='student_id')
            .merge(lottery_df, on='student_id')
        )
        # Introduce jitter
        merged = merged.copy()
        merged['_j'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))*0.01
        merged = merged.sort_values('_j').drop(columns=['_j'])

        # Allocate
        for _, row in merged.iterrows():
            sid  = row['student_id']
            term = row['term']
            used = set()
            placed = False
            allowed_map = term_prefs.get(sid, {})
            default_terms = student_terms_map.get(sid, [])

            for i in range(1, MAX_HOPES+1):
                dept = row.get(f'hope_{i}')
                if not dept or dept in used:
                    continue
                # If dept has specified terms use them, otherwise use default student terms
                allowed_terms = allowed_map.get(dept, default_terms)
                if term not in allowed_terms:
                    continue
                key = (dept, f'term_{term}')
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    used.add(dept)
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
                # Fallback remains unchanged
                assignment.append({
                    'student_id': sid,
                    'term': term,
                    'assigned_department': '未配属',
                    'hope_rank': None,
                    'is_imputed': bool(row.get('is_imputed', False))
                })
    return pd.DataFrame(assignment)
