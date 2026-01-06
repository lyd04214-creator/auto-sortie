import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_full_history():
    print("🚀 [System] 데이터 재생성 시작 (컬럼 누락 수정판)...")
    
    # 1. 기지 정보 로드
    try:
        df_bases = pd.read_csv('data/bases.csv', encoding='utf-8')
    except:
        df_bases = pd.read_csv('data/bases.csv', encoding='cp949')
    target_bases = df_bases['base_name'].unique().tolist()

    # 2. 시나리오 데이터 로드
    try:
        df_scenario = pd.read_csv('data/scenario_data.csv', encoding='utf-8')
    except:
        df_scenario = pd.read_csv('data/scenario_data.csv', encoding='cp949')

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today - timedelta(days=364)
    records = []
    
    # --- [Phase 1] 과거 데이터 (랜덤) ---
    print("   - 과거 1년치 데이터 생성 중...")
    current_date = start_date
    while current_date < today:
        date_str = current_date.strftime("%Y-%m-%d")
        for base in target_bases:
            # 활동성 설정
            if any(k in base for k in ['Sunchon', 'Pukchang', 'Taetan', 'Sunan']):
                avg, vol = 15, 6
            else:
                avg, vol = 2, 2
            
            prev_count = int(np.random.normal(avg, vol))
            for h in range(0, 24, 2):
                time_str = f"{h:02d}:00"
                count = max(0, min(30, int(np.random.normal(avg, vol))))
                records.append({
                    'datetime': f"{date_str} {time_str}",
                    'date': date_str,      # [복구] 필수 컬럼
                    'time': time_str,      # [복구] 필수 컬럼
                    'base_name': base,
                    'total_count': count,
                    'status': "ALERT" if abs(count - prev_count) >= 4 else "STABLE",
                    'diff': count - prev_count
                })
                prev_count = count
        current_date += timedelta(days=1)

    # --- [Phase 2] 오늘 데이터 (시나리오) ---
    print("   - 오늘(Scenario) 데이터 생성 중...")
    today_str = today.strftime("%Y-%m-%d")
    
    for base in target_bases:
        # 시나리오 매칭
        scenario_subset = pd.DataFrame()
        if not df_scenario.empty:
            scenario_subset = df_scenario[df_scenario['base_name'] == base]
            if scenario_subset.empty: # 부분 일치 검색
                simple_name = base.split(' ')[0]
                scenario_subset = df_scenario[df_scenario['base_name'] == simple_name]
        
        # 시나리오 없음 -> 랜덤 (Group B)
        if scenario_subset.empty:
            prev_count = 2
            for h in range(0, 24, 2):
                time_str = f"{h:02d}:00"
                count = 2 + np.random.randint(-1, 2)
                records.append({
                    'datetime': f"{today_str} {time_str}",
                    'date': today_str,    # [복구]
                    'time': time_str,     # [복구]
                    'base_name': base,
                    'total_count': count,
                    'status': "STABLE",
                    'diff': count - prev_count
                })
                prev_count = count
        else:
            # 시나리오 적용 (Group A)
            scenario_subset = scenario_subset.sort_values('time')
            prev_count = scenario_subset.iloc[0]['total_count']
            
            for _, row in scenario_subset.iterrows():
                time_str = row['time']
                count = row['total_count']
                
                if time_str == "00:00": diff = 0
                else: diff = count - prev_count
                
                records.append({
                    'datetime': f"{today_str} {time_str}",
                    'date': today_str,    # [복구]
                    'time': time_str,     # [복구]
                    'base_name': base,
                    'total_count': count,
                    'status': "ALERT" if abs(diff) >= 4 else "STABLE",
                    'diff': diff
                })
                prev_count = count

    # 저장
    df_res = pd.DataFrame(records)
    df_res.sort_values('datetime', inplace=True)
    df_res.to_csv('data/historical_stats.csv', index=False, encoding='utf-8-sig')
    print(f"✅ 데이터 재생성 완료! (총 {len(df_res)}건)")

if __name__ == "__main__":
    generate_full_history()