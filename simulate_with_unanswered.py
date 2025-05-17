import pandas as pd
import random
import numpy as np
import re
from collections import defaultdict

def parse_term_list(raw, default_terms):
    if pd.isna(raw) or not str(raw).strip():
        return None
    nums  = [int(n) for n in re.findall(r"\d+", str(raw))]
    valid = [n for n in nums if n in default_terms]
    return sorted(set(valid)) if valid else None

def run_simulation(responses_base: pd.DataFrame,
                   lottery_df: pd.DataFrame,
                   capacity_df: pd.DataFrame,
                   terms_df: pd.DataFrame,
                   hist_df=None) -> pd.DataFrame:
    # --- hope 列 と MAX_HOPES取得 ---
    hope_cols = [c for c in responses_base.columns
                 if c.startswith('hope_') and not c.endswith('_terms')]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)
    term_labels = [c for c in terms_df.columns if c.startswith('term_')]

    # --- student_terms_map ---
    student_terms_map = {
        row['student_id']: [
            int(row[col]) for col in term_labels
            if pd.notna(row[col]) and re.search(r'\d+', str(row[col]))
        ]
        for _, row in terms_df.iterrows()
    }

    # --- term_prefs 構築 ---
    term_prefs = {}
    for _, row in responses_base.iterrows():
        sid = row['student_id']
        default_terms = student_terms_map.get(sid, [])
        prefs = {}
        for i in range(1, MAX_HOPES+1):
            dept = row.get(f'hope_{i}')
            raw  = row.get(f'hope_{i}_terms')
            valid = parse_term_list(raw, default_terms)
            if valid:
                prefs[dept] = valid
        term_prefs[sid] = prefs

    # --- popularity scoring (既存) ---
    pop = defaultdict(int)
    for i in range(1, MAX_HOPES+1):
        w = MAX_HOPES + 1 - i
        for dept in responses_base.get(f'hope_{i}', pd.Series()).dropna():
            if dept and dept != '-':
                pop[dept] += w

    answered_ids = set(responses_base['student_id'])
    all_ids      = set(terms_df['student_id'])
    unresp_ids   = list(all_ids - answered_ids)

    dept_list, counts = zip(*pop.items())
    weights = [c / sum(counts) for c in counts]

    # --- 非回答者の imputation (既存) ---
    imputed = []
    for sid in unresp_ids:
        picks = []
        while len(picks) < MAX_HOPES:
            choice = random.choices(dept_list, weights=weights, k=1)[0]
            if choice not in picks:
                picks.append(choice)
        row = {'student_id': sid}
        for idx, d in enumerate(picks, start=1):
            row[f'hope_{idx}'] = d
        row['is_imputed'] = True
        imputed.append(row)
    imputed_df = pd.DataFrame(imputed)

    # --- 結合 ---
    real_df = responses_base.copy()
    real_df['is_imputed'] = False
    all_resp = pd.concat([real_df, imputed_df], ignore_index=True)

    # --- 割当シミュレーション ---
    assignment = []
    for term_label in term_labels:
        # キャパシティ初期化
        cap = {}
        for _, r in capacity_df.iterrows():
            dept = r['hospital_department']
            for tcol in term_labels:
                cap[(dept, tcol)] = int(r[tcol]) if not pd.isna(r[tcol]) else 0

        # マージ & ソート
        term_map = terms_df[['student_id', term_label]].rename(columns={term_label: 'term'})
        term_map['term'] = term_map['term'].astype(int)
        merged = (
            all_resp
            .merge(term_map, on='student_id')
            .merge(lottery_df, on='student_id')
        )
        merged['_j'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))*0.01
        merged = merged.sort_values('_j').drop(columns=['_j'])

        # 各 row ごとに割当
        assigned = {}
        for _, row in merged.iterrows():
            sid  = row['student_id']
            term = row['term']
            used = assigned.get(sid, set())
            placed = False
            default_terms = student_terms_map.get(sid, [])
            prefs = term_prefs.get(sid, {})

            for i in range(1, MAX_HOPES+1):
                dept = row.get(f'hope_{i}')
                if not dept or dept in used:
                    continue
                # ターム指定反映
                allowed = prefs.get(dept, default_terms)
                if term not in allowed:
                    continue

                key = (dept, term_label)
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
