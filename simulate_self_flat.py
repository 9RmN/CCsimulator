# simulate_self_flat.py
import pandas as pd
import random
from collections import defaultdict

N_SIMULATIONS = 300

def simulate_self_flat(student_id):
    # データ読み込み
    responses = pd.read_csv("responses.csv", dtype={'student_id': str})
    lottery = pd.read_csv("lottery_order.csv", dtype={'student_id': str})
    terms = pd.read_csv("student_terms.csv", dtype={'student_id': str})
    capacity = pd.read_csv("department_capacity.csv")
    
    # student_id の希望一覧
    self_row = responses[responses["student_id"] == student_id]
    if self_row.empty:
        raise ValueError("student_id が responses.csv に存在しません")

    # 希望一覧（重複除く、空白・"-"除く）
    hopes = self_row.iloc[0].drop(labels="student_id").dropna().unique()
    hopes = [h for h in hopes if h != "-" and h.strip() != ""]

    if len(hopes) == 0:
        raise ValueError("希望が入力されていません")

    # 自分の term を取得
    my_terms = terms[terms["student_id"] == student_id].iloc[0][["term_1", "term_2", "term_3", "term_4"]].values
    my_lottery = int(lottery[lottery["student_id"] == student_id]["lottery_order"].iloc[0])

    # 他学生（自分以外）の responses を取得
    others = responses[responses["student_id"] != student_id]

    # popularity スコア計算
    popularity = defaultdict(int)
    MAX_HOPES = 20
    for i in range(1, MAX_HOPES + 1):
        w = MAX_HOPES + 1 - i
        col = f"hope_{i}"
        if col in others.columns:
            for dept in others[col].dropna():
                if dept != "-" and dept.strip() != "":
                    popularity[dept] += w

    # 未回答者を抽出
    answered_ids = set(others["student_id"])
    all_ids = set(terms["student_id"])
    unanswered_ids = list(all_ids - answered_ids - {student_id})
    unanswered_df = lottery[lottery["student_id"].isin(unanswered_ids)]

    # popularityから未回答者の希望を生成
    generated_rows = []
    if popularity:
        depts, weights = zip(*[(d, v / sum(popularity.values())) for d, v in popularity.items()])
        for uid in unanswered_df["student_id"]:
            row = {"student_id": uid}
            picks = random.choices(depts, weights=weights, k=MAX_HOPES)
            for i, dept in enumerate(picks, 1):
                row[f"hope_{i}"] = dept
            generated_rows.append(row)
    generated = pd.DataFrame(generated_rows)

    # responses統合
    full_responses = pd.concat([others, generated], ignore_index=True)

    # term情報と抽選順位を付加
    merged = full_responses.merge(terms, on="student_id").merge(lottery, on="student_id")

    # 希望ごとの通過回数記録用
    count = {dept: 0 for dept in hopes}

    for _ in range(N_SIMULATIONS):
        # term ごとの残数を初期化
        cap = {}
        for _, r in capacity.iterrows():
            dept = r["hospital_department"]
            for t in capacity.columns[1:]:
                cap[(dept, t)] = r[t]

        student_assigned = {}

        # 他学生の配属処理
        merged_sorted = merged.sort_values("lottery_order")
        for _, r in merged_sorted.iterrows():
            sid = r["student_id"]
            term_list = [r[f"term_{i}"] for i in range(1, 5)]
            used = student_assigned.get(sid, set())
            for term in term_list:
                for i in range(1, MAX_HOPES + 1):
                    d = r.get(f"hope_{i}", "")
                    if pd.isna(d) or d in used or d not in cap: continue
                    key = (d, f"term_{term}")
                    if cap.get(key, 0) > 0:
                        cap[key] -= 1
                        used.add(d)
                        student_assigned[sid] = used
                        break

        # 自分を順位無視で term 1〜4 に割り当て
        used = set()
        for term in my_terms:
            for d in hopes:
                if d in used: continue
                key = (d, f"term_{term}")
                if cap.get(key, 0) > 0:
                    cap[key] -= 1
                    used.add(d)
                    count[d] += 1
                    break

    # 確率に変換
    result = pd.DataFrame([
        {"希望科": d, "通過確率（順位無視）": f"{(count[d] / N_SIMULATIONS * 100):.1f}%"}
        for d in hopes
    ])

    return result
