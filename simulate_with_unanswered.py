# simulate_with_unanswered.py
import pandas as pd
import random
from collections import defaultdict

def run_simulation(responses_base, lottery_df, capacity_df, terms_df):
    # responses_base は一度だけ読み込んだ DataFrame
    # lottery_df, capacity_df, terms_df も同様

    MAX_HOPES = max(int(c.split('_')[1]) for c in responses_base if c.startswith('hope_'))
    TERM_LABELS = ["term_1", "term_2", "term_3", "term_4"]

    # popularity は実データのみで重み付け済みの responses_base を使って計算済みでも OK
    # ここでは省略しつつ、元の実装どおり生成
    popularity = defaultdict(int)
    for i in range(1, MAX_HOPES+1):
        w0 = MAX_HOPES+1 - i
        for dept in responses_base[f"hope_{i}"].dropna():
            popularity[dept] += w0

    # 未回答者抽出
    answered_ids   = set(responses_base["student_id"])
    all_ids        = set(terms_df["student_id"])
    unresp_ids     = list(all_ids - answered_ids)
    unresp_df      = lottery_df[lottery_df["student_id"].isin(unresp_ids)]

    # 生成
    generated = []
    depts, weights = zip(*[(d, v/sum(popularity.values())) for d,v in popularity.items()])
    for sid in unresp_df["student_id"]:
        row = {"student_id": sid}
        picks = random.choices(depts, weights=weights, k=MAX_HOPES)
        for idx, dept in enumerate(picks, start=1):
            row[f"hope_{idx}"] = dept
        generated.append(row)
    gen_df = pd.DataFrame(generated)
    gen_df['is_imputed']   = True
    base_df = responses_base.copy()
    base_df['is_imputed']  = False
    all_responses = pd.concat([base_df, gen_df], ignore_index=True)

    # ここから initial_assignment と同じロジック。
    # all_responses, lottery_df, capacity_df, terms_df を使って
    # assignment_result を DataFrame として返す。
    assignment_result = []
    cap = {}
    for _, r in capacity_df.iterrows():
        dept = r["hospital_department"]
        for t in capacity_df.columns[1:]:
            cap[(dept, t)] = r[t]
    student_assigned = {}

    for term_label in TERM_LABELS:
        tm = terms_df[["student_id", term_label]].rename(columns={term_label:"term"})
        resp_term = all_responses.merge(tm, on="student_id")
        merged    = resp_term.merge(lottery_df, on="student_id").sort_values("lottery_order")

        for _, r in merged.iterrows():
            sid  = r["student_id"]
            term = r["term"]
            used = student_assigned.get(sid,set())
            for i in range(1, MAX_HOPES+1):
                d = r[f"hope_{i}"]
                if pd.isna(d) or d in used: continue
                key = (d, f"term_{term}")
                if cap.get(key,0)>0:
                    cap[key] -= 1
                    assignment_result.append({
                        "student_id": sid,
                        "term": term,
                        "assigned_department": d,
                        "hope_rank": i,
                        "is_imputed": r["is_imputed"]
                    })
                    used.add(d)
                    student_assigned[sid]=used
                    break
            else:
                assignment_result.append({
                    "student_id": sid,
                    "term": term,
                    "assigned_department": "未配属",
                    "hope_rank": None,
                    "is_imputed": r["is_imputed"]
                })

    return pd.DataFrame(assignment_result)
