import pandas as pd
import numpy as np
import random
from collections import defaultdict

# モンテカルロ回数
N_SIMULATIONS = 100

def simulate_each_as_first(student_id: str) -> pd.DataFrame:
    """
    指定した学生IDについて、各希望科を第1希望とした場合の通過確率を推定する。
    """
    # --- データ読み込み ---
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery   = pd.read_csv("lottery_order.csv", dtype={'student_id': str, 'lottery_order': int})
    terms     = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity  = pd.read_csv("department_capacity.csv")

    # 自分の希望
    me = responses[responses['student_id'] == student_id]
    if me.empty:
        raise ValueError(f"student_id {student_id} が見つかりません。")
    hope_cols = [c for c in responses.columns if c.startswith('hope_')]
    hopes = [h for h in me[hope_cols].iloc[0].dropna().tolist() if h and h != '-']
    if not hopes:
        raise ValueError("希望が登録されていません。")

    # 他学生 + 補完
    others = responses[responses['student_id'] != student_id]
    # popularity
    MAX_HOPES = len(hope_cols)
    pop = defaultdict(int)
    for i, col in enumerate(hope_cols, start=1):
        w = MAX_HOPES + 1 - i
        for d in others[col].dropna():
            if d and d != '-':
                pop[d] += w
    dept_list, counts = zip(*pop.items())
    total = sum(counts)
    weights = [c/total for c in counts]

    # 未回答者の補完
    answered_ids = set(others['student_id'])
    all_ids      = set(terms['student_id'])
    unresp       = list(all_ids - answered_ids - {student_id})
    gen_rows = []
    for uid in unresp:
        picks = []
        while len(picks) < MAX_HOPES:
            choice = random.choices(dept_list, weights=weights, k=1)[0]
            if choice not in picks:
                picks.append(choice)
        row = {'student_id': uid}
        for idx, d in enumerate(picks, start=1):
            row[f'hope_{idx}'] = d
        gen_rows.append(row)
    gen_df = pd.DataFrame(gen_rows)
    full_responses = pd.concat([others, gen_df], ignore_index=True)

    # terms+lottery
    terms_lot = terms.merge(lottery, on='student_id')

    results = []
    for target in hopes:
        success = 0
        for _ in range(N_SIMULATIONS):
            # capacity reset
            cap = { (r['hospital_department'], t): int(r[t]) if not pd.isna(r[t]) else 0
                   for _, r in capacity.iterrows() for t in capacity.columns[1:] }

            # 他学生割当
            merged = full_responses.merge(terms_lot, on='student_id')
            # ジッターを加えて順序を微調整
            merged = merged.copy()
            merged['_ord'] = merged['lottery_order'].astype(float) + np.random.rand(len(merged))*0.01
            merged = merged.sort_values('_ord')

            # 割当
            assigned = {}
            for _, r in merged.iterrows():
                sid = r['student_id']
                used = assigned.get(sid, set())
                # student_terms.csv の term_1～term_4 を順に試し、いずれかの月で配属を試みる
                for term_idx in range(1, 5):
                    term_month = r.get(f'term_{term_idx}')
                    if pd.isna(term_month):
                        continue
                    for i in range(1, MAX_HOPES+1):
                        dept = r.get(f'hope_{i}', '')
                        if not dept or dept in used:
                            continue
                        key = (dept, f'term_{int(term_month)}')
                        if cap.get(key, 0) > 0:
                            cap[key] -= 1
                            assigned.setdefault(sid, set()).add(dept)
                            break
                    # １つでも配属できたら、次の学生へ
                    if sid in assigned and assigned[sid]:
                        break

            # 自分の配当判定
            my_terms = terms.loc[terms['student_id']==student_id].iloc[0]
            for term_idx in range(1, 5):
                month = my_terms.get(f'term_{term_idx}')
                if pd.isna(month):
                    continue
                if cap.get((target, f'term_{int(month)}'), 0) > 0:
                    success += 1
                    break

        pct = round(success / N_SIMULATIONS * 100, 1)
        results.append({
            'student_id': student_id,
            '希望科': target,
            '通過確率': pct
        })

    return pd.DataFrame(results)

# === CLI: 並列で全回答者分を一気に生成 ===
if __name__ == '__main__':
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    resp = pd.read_csv('responses.csv', dtype={'student_id': str})
    sids = resp['student_id'].tolist()

    output = []
    workers = min(4, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(simulate_each_as_first, sid): sid for sid in sids}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                df = fut.result()
                output.append(df)
                print(f"{sid}: done")
            except Exception as e:
                print(f"{sid}: error {e}")
    # 結合と保存
    all_df = pd.concat(output, ignore_index=True)
    all_df.to_csv('first_choice_probabilities.csv', index=False)
    print('All first choice probabilities generated.')
