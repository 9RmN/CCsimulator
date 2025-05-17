import pandas as pd
import numpy as np
import random
import re
from collections import defaultdict

# モンテカルロ回数
N_SIMULATIONS = 30

def parse_term_list(raw, default_terms):
    """
    raw: e.g. "[9, 10]" や "2;5" や ""/NaN
    default_terms: その学生の基本４タームリスト
    戻り値: 指定タームのリスト（昇順）、指定なし／不正入力時は None
    """
    if pd.isna(raw) or not str(raw).strip():
        return None
    nums = [int(n) for n in re.findall(r"\d+", str(raw))]
    valid = [n for n in nums if n in default_terms]
    return sorted(set(valid)) if valid else None

def simulate_each_as_first(student_id: str) -> pd.DataFrame:
    # --- データ読み込み ---
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery   = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    terms_df  = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity  = pd.read_csv("department_capacity.csv", dtype=str)

    # --- student_terms_map の構築 ---
    student_terms_map = {
        row['student_id']: [
            int(row[f'term_{i}']) for i in range(1,5)
            if pd.notna(row.get(f'term_{i}')) and re.search(r'\d+', str(row[f'term_{i}']))
        ]
        for _, row in terms_df.iterrows()
    }

    # --- 希望列と最大希望数の取得 ---
    hope_cols = [c for c in responses.columns if c.startswith('hope_') and not c.endswith('_terms')]
    MAX_HOPES = max(int(c.split('_')[1]) for c in hope_cols)

    # --- term_prefs の構築 (sid -> {dept: [terms]}) ---
    term_prefs = {}
    for _, row in responses.iterrows():
        sid = row['student_id']
        default_terms = student_terms_map.get(sid, [])
        prefs = {}
        for i in range(1, MAX_HOPES+1):
            dept = row.get(f'hope_{i}')
            raw  = row.get(f'hope_{i}_terms')
            if pd.isna(dept) or not str(dept).strip() or pd.isna(raw):
                continue
            valid_terms = parse_term_list(raw, default_terms)
            if valid_terms:
                prefs[dept] = valid_terms
        term_prefs[sid] = prefs

    # --- 自分の希望取得 ---
    me = responses.loc[responses['student_id'] == student_id]
    if me.empty:
        raise ValueError(f"student_id {student_id} が見つかりません。")
    hopes = [h for h in me.iloc[0][hope_cols].dropna().tolist() if h and h != '-']

    # --- 他学生 & 未回答者リスト ---
    others       = responses[responses['student_id'] != student_id]
    answered_ids = set(others['student_id'])
    all_ids      = set(terms_df['student_id'])
    unresp_ids   = list(all_ids - answered_ids - {student_id})

    # --- popularity 重み付け ---
    pop = defaultdict(int)
    for idx, col in enumerate(hope_cols, start=1):
        weight = MAX_HOPES + 1 - idx
        for d in others[col].dropna():
            if d and d != '-':
                pop[d] += weight
    dept_list, counts = zip(*pop.items())
    weights = [c / sum(counts) for c in counts]

    # --- terms + lottery 結合 ---
    terms_lot = terms_df.merge(lottery, on='student_id')

    results = []
    for target in hopes:
        success = 0
        for _ in range(N_SIMULATIONS):
            # --- capacity リセット ---
            cap = {}
            for _, r in capacity.iterrows():
                dept = r['hospital_department']
                for col in capacity.columns[1:]:
                    m = re.search(r'\d+', col)
                    if not m: continue
                    tnum = int(m.group())
                    cap[(dept, tnum)] = int(r[col]) if pd.notna(r[col]) and str(r[col]).isdigit() else 0

            # --- 未回答者の希望補完 ---
            gen_rows = []
            for uid in unresp_ids:
                picks = []
                while len(picks) < MAX_HOPES:
                    choice = random.choices(dept_list, weights=weights, k=1)[0]
                    if choice not in picks:
                        picks.append(choice)
                row = {'student_id': uid}
                for i, d in enumerate(picks, start=1):
                    row[f'hope_{i}'] = d
                gen_rows.append(row)
            gen_df = pd.DataFrame(gen_rows)

            # --- 自分のダミー希望 ---
            dummy = {'student_id': student_id}
            for c in hope_cols:
                dummy[c] = ''
            dummy[hope_cols[0]] = target
            me_dummy = pd.DataFrame([dummy])

            # --- 全体データ組立 & ソート ---
            full = pd.concat([others, gen_df, me_dummy], ignore_index=True)
            merged = full.merge(terms_lot, on='student_id')
            merged['_ord'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))*0.01
            merged = merged.sort_values('_ord').drop(columns=['_ord'])

            # --- 割当シミュレーション ---
            assigned = {}
            for _, r in merged.iterrows():
                sid = r['student_id']
                used = assigned.get(sid, set())
                placed = False

                # 4つの term_1～term_4
                for ti in range(1,5):
                    term_month = r.get(f'term_{ti}')
                    if pd.isna(term_month):
                        continue
                    term_month = int(term_month)

                    # 希望順位ループ
                    default_terms = student_terms_map.get(sid, [])
                    prefs = term_prefs.get(sid, {})
                    for i in range(1, MAX_HOPES+1):
                        dept = r.get(f'hope_{i}', '')
                        if not dept or dept in used:
                            continue
                        allowed = prefs.get(dept, default_terms)
                        if term_month not in allowed:
                            continue
                        key = (dept, term_month)
                        if cap.get(key, 0) > 0:
                            cap[key] -= 1
                            used.add(dept)
                            assigned[sid] = used
                            if sid == student_id and dept == target:
                                success += 1
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break

        pct = round(success / N_SIMULATIONS * 100, 1)
        results.append({'student_id': student_id, '希望科': target, '通過確率': pct})

    return pd.DataFrame(results)

if __name__ == '__main__':
    # …（もとの CLI 部分をそのまま） …
    pass
