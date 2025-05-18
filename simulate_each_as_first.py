import pandas as pd
import numpy as np
import random
import re
from collections import defaultdict

N_SIMULATIONS = 20

def parse_term_list(raw, default_terms):
    if pd.isna(raw) or not str(raw).strip():
        return None
    nums = [int(n) for n in re.findall(r"\d+", str(raw))]
    valid = [n for n in nums if n in default_terms]
    return sorted(set(valid)) if valid else None

def simulate_each_as_first(student_id: str) -> pd.DataFrame:
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    terms_df = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity = pd.read_csv("department_capacity.csv", dtype=str)

    student_terms_map = {
        row['student_id']: [
            int(row[f'term_{i}']) for i in range(1, 5)
            if pd.notna(row.get(f'term_{i}')) and re.search(r'\d+', str(row[f'term_{i}']))
        ]
        for _, row in terms_df.iterrows()
    }

    hope_cols = [c for c in responses.columns if c.startswith('hope_') and not c.endswith('_terms')]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)

    term_prefs = {}
    for _, row in responses.iterrows():
        sid = row['student_id']
        default_terms = student_terms_map.get(sid, [])
        prefs = {}
        for i in range(1, MAX_HOPES+1):
            dept = row.get(f'hope_{i}')
            raw = row.get(f'hope_{i}_terms')
            if pd.isna(dept) or not str(dept).strip() or pd.isna(raw):
                continue
            valid_terms = parse_term_list(raw, default_terms)
            if valid_terms:
                prefs[dept] = valid_terms
        term_prefs[sid] = prefs

    me = responses.loc[responses['student_id'] == student_id]
    if me.empty:
        raise ValueError(f"student_id {student_id} が見つかりません。")
    original_hopes = [h for h in me.iloc[0][hope_cols].dropna().tolist() if h and h != '-']

    others = responses[responses['student_id'] != student_id]
    answered_ids = set(others['student_id'])
    all_ids = set(terms_df['student_id'])
    unresp_ids = list(all_ids - answered_ids - {student_id})

    pop = defaultdict(int)
    for idx, col in enumerate(hope_cols, start=1):
        weight = MAX_HOPES + 1 - idx
        for d in others[col].dropna():
            if d and d != '-':
                pop[d] += weight
    dept_list, counts = zip(*pop.items())
    weights = [c / sum(counts) for c in counts]

    terms_lot = terms_df.merge(lottery, on='student_id')

    results = []
    for target in original_hopes:
        success = 0
        for _ in range(N_SIMULATIONS):
            cap = {
                (r['hospital_department'], int(re.search(r'\d+', col).group())): int(r[col])
                for _, r in capacity.iterrows() for col in capacity.columns[1:]
                if re.search(r'\d+', col) and pd.notna(r[col]) and str(r[col]).isdigit()
            }

            gen_rows = []
            for uid in unresp_ids:
                picks = random.sample(dept_list, MAX_HOPES)
                row = {'student_id': uid, **{f'hope_{i}': picks[i-1] for i in range(1, MAX_HOPES+1)}}
                gen_rows.append(row)
            gen_df = pd.DataFrame(gen_rows)

            dummy = {'student_id': student_id}
            new_hopes = [target] + [dept for dept in original_hopes if dept != target]
            for i, dept in enumerate(new_hopes, 1):
                dummy[f'hope_{i}'] = dept
            for i in range(len(new_hopes)+1, MAX_HOPES+1):
                dummy[f'hope_{i}'] = ''
            me_dummy = pd.DataFrame([dummy])

            full = pd.concat([others, gen_df, me_dummy], ignore_index=True)
            merged = full.merge(terms_lot, on='student_id')
            merged['_ord'] = merged['lottery_order'] + np.random.rand(len(merged))*0.01
            merged = merged.sort_values('_ord').drop(columns=['_ord'])

            assigned = defaultdict(set)  # 修正箇所: defaultdict(set) を使用
            for _, r in merged.iterrows():
                sid = r['student_id']
                used = assigned[sid]  # 修正箇所: 正しくsetを初期化
                placed = False

                for ti in range(1, 5):
                    if placed:
                        break
                    term_month = r.get(f'term_{ti}')
                    if pd.isna(term_month):
                        continue
                    term_month = int(term_month)
                    default_terms = student_terms_map.get(sid, [])
                    prefs = term_prefs.get(sid, {})
                    for i in range(1, MAX_HOPES+1):
                        dept = r.get(f'hope_{i}', '')
                        if not dept or dept in used:
                            continue
                        allowed = prefs.get(dept, default_terms)
                        if term_month not in allowed:
                            continue
                        if cap.get((dept, term_month), 0) > 0:
                            cap[(dept, term_month)] -= 1
                            used.add(dept)
                            if sid == student_id and dept == target:
                                success += 1
                            placed = True
                            break

        pct = round(success / N_SIMULATIONS * 100, 1)
        results.append({'student_id': student_id, '希望科': target, '通過確率': pct})

    return pd.DataFrame(results)

if __name__ == '__main__':
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    all_students = responses['student_id'].unique()
    final_results = pd.concat([simulate_each_as_first(sid) for sid in all_students])
    final_results.to_csv("first_choice_probabilities.csv", index=False)
