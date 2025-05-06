import pandas as pd

def main():
    # 割当結果と抽選順位を読み込む
    assign_df = pd.read_csv("assignment_with_unanswered.csv", dtype={'student_id': str})
    lottery_df = pd.read_csv("lottery_order.csv", dtype={'student_id': str})

    # マージして中央値を算出
    merged = assign_df.merge(lottery_df, on='student_id')
    pop_rank = (
        merged.groupby('assigned_department')['lottery_order']
        .median()
        .reset_index()
        .rename(columns={'lottery_order': '抽選順位中央値'})
    )

    pop_rank.to_csv("popular_departments_rank_combined.csv", index=False)
    print("Generated popular_departments_rank_combined.csv")

if __name__ == '__main__':
    main()
