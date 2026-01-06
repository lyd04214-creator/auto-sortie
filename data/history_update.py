import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 1. 기지별 평시(Normal) 기준값 설정
# (기지명: [Fighter, Bomber, Transport, Civil, Noise_Level])
# Noise_Level: 0(변동없음), 1(가끔 변동), 2(자주 변동)
base_config = {
    # [Group A] 핵심 기지
    "Sunchon":  [4, 0, 0, 0, 0],  # 평소 4대 고정
    "Pukchang": [8, 0, 0, 0, 1],  # 평소 8대, 가끔 훈련
    "Taetan":   [0, 0, 0, 0, 0],  # 평소 0대 (Empty)
    "Sunan":    [0, 0, 1, 2, 1],  # 평소 3대 (수송1+민항2)

    # [Group B] 기타 기지 (Static)
    "Onchon":   [3, 0, 0, 0, 0],
    "Hwangju":  [3, 0, 0, 0, 0],
    "Koksan":   [3, 0, 1, 0, 0],  # Fighter 3 + Trans 1
    "Wonsan":   [3, 0, 0, 0, 0],
    "Sondok":   [0, 0, 1, 0, 0],  # Trans 1 (An-2)
    "Uiju":     [0, 3, 0, 0, 0],  # Bomber 3
    "Jangjin":  [0, 0, 0, 4, 0],  # Trainer 4 (Civil/Trainer 분류가 애매하면 Civil로 일단 처리 or Fighter로) -> 여기선 Civil로 가정
    "Toksan":   [3, 0, 0, 0, 0],
    "Kwail":    [3, 0, 0, 0, 0],
    "Orang":    [3, 0, 0, 0, 0],
    "Kaechon":  [3, 0, 0, 0, 0],
    "Samjiyon": [3, 0, 0, 0, 0],
    
    # Empty Bases
    "Hwangsuwon": [0, 0, 0, 0, 0],
    "Taechon":    [0, 0, 0, 0, 0],
    "Hyesan":     [0, 0, 0, 0, 0],
    "Kowon":      [0, 0, 0, 0, 0],
    "Nuchon":     [0, 0, 0, 0, 0],
    "Hyonli":     [0, 0, 0, 0, 0],
    
    # CSV에 있었던 추가 기지 (기존 데이터 유지)
    "Kilchu":     [0, 0, 2, 0, 0],
    "Yonpo":      [0, 0, 2, 0, 0],
    "Samjangcol": [0, 0, 2, 0, 0],
}

# 2. 날짜 생성 (2024-12-01 ~ 2026-01-10)
start_date = datetime(2024, 12, 1)
end_date = datetime(2026, 1, 10)
date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
time_steps = ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00", 
              "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]

# 3. 데이터 생성 함수
data_rows = []

np.random.seed(42) # 재현성 확보

for date_obj in date_range:
    date_str = date_obj.strftime("%Y-%m-%d")
    
    # 하루 단위로 기본 변동성 적용 여부 결정 (너무 자주 바뀌면 정신없음)
    daily_noise_factor = np.random.rand() 
    
    for time_str in time_steps:
        full_datetime = f"{date_str} {time_str}"
        
        for base, config in base_config.items():
            f, b, t, c, noise_lvl = config
            
            # 노이즈 적용 로직 (Pukchang, Sunan 등만 해당)
            # Noise Level 1: 5% 확률로 +1 or -1 변동
            current_f, current_b, current_t, current_c = f, b, t, c
            
            if noise_lvl == 1:
                if np.random.rand() < 0.05: # 5% 확률로 이벤트 발생
                    change = np.random.choice([-1, 1])
                    # Fighter가 주력이면 Fighter를 변동
                    if f > 0: 
                        current_f = max(0, f + change)
                    # Civil/Trans 위주면 그쪽 변동 (Sunan)
                    elif t > 0 or c > 0:
                        current_c = max(0, c + change)

            total = current_f + current_b + current_t + current_c
            
            # 이미지 경로는 가상의 경로 할당
            img_path = f"{base.lower()}_t1.png"
            
            data_rows.append({
                "datetime": full_datetime,
                "date": date_str,
                "time": time_str,
                "base_name": base,
                "cnt_fighter": current_f,
                "cnt_bomber": current_b,
                "cnt_transport": current_t,
                "cnt_civil": current_c,
                "total_count": total,
                "img_path": img_path
            })

# 4. DataFrame 변환
df = pd.DataFrame(data_rows)

# 5. Diff 및 Status 계산 (기지별 시간순 정렬 필수)
df = df.sort_values(by=['base_name', 'datetime']).reset_index(drop=True)

# Diff: 현재 total_count - 이전 total_count
df['diff'] = df.groupby('base_name')['total_count'].diff().fillna(0).astype(int)

# Status: 변화가 없으면 STABLE, 있으면 ALERT
df['status'] = df['diff'].apply(lambda x: 'ALERT' if x != 0 else 'STABLE')

# 6. 컬럼 순서 정리
final_cols = ["datetime", "date", "time", "base_name", "cnt_fighter", "cnt_bomber", 
              "cnt_transport", "cnt_civil", "total_count", "status", "diff", "img_path"]
df_final = df[final_cols]

# 7. 결과 확인 및 저장 안내
print(f"생성된 데이터 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
print(f"총 데이터 행 수: {len(df_final)}개")
print("샘플 데이터(상위 5행):")
print(df_final.head())

# CSV 파일 저장 (필요시 주석 해제)
df_final.to_csv("defense_base_history_202412_202601.csv", index=False, encoding='utf-8-sig')