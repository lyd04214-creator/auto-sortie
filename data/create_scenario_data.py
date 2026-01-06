import pandas as pd
import numpy as np
import os

# 폴더 확인
if not os.path.exists('data'):
    os.makedirs('data')

# 시간대 정의 (2시간 간격)
times = ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]

# 데이터 담을 리스트
data_rows = []

# ---------------------------------------------------------
# 1. 핵심 기지 (Scenario Active) - 변화 있음
# ---------------------------------------------------------

# (1) 순천 (Sunchon) - 이탈
# 00-08: 4, 10: 6, 12-16: 2, 18-22: 3
sunchon_fighter = [4, 4, 4, 4, 4, 6, 2, 2, 2, 3, 3, 3]
sunchon_su25    = [0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0] # 설명에 따른 보조 (여기선 fighter 합계로 퉁치거나 별도 관리 가능. 일단 fighter 총합으로 계산)
# 위 리스트 자체가 fighter 총합이라고 가정하고 진행 (표에 있는 숫자 그대로)

for i, t in enumerate(times):
    data_rows.append({'base_name': 'Sunchon', 'time': t, 'cnt_fighter': sunchon_fighter[i], 'cnt_bomber': 0, 'cnt_transport': 0, 'cnt_civil': 0, 'cnt_trainer': 0})

# (2) 태탄 (Taetan) - 침투
# 00-12: 0, 14: 4, 16-18: 4(F)+1(T), 20-22: 2(F)+1(T)
taetan_fighter = [0, 0, 0, 0, 0, 0, 0, 4, 4, 4, 2, 2]
taetan_trans   = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]

for i, t in enumerate(times):
    data_rows.append({'base_name': 'Taetan', 'time': t, 'cnt_fighter': taetan_fighter[i], 'cnt_bomber': 0, 'cnt_transport': taetan_trans[i], 'cnt_civil': 0, 'cnt_trainer': 0})

# (3) 북창 (Pukchang) - 훈련
# 00-08: 8, 10: 12, 12-14: 4, 16-22: 10
pukchang_fighter = [8, 8, 8, 8, 8, 12, 4, 4, 10, 10, 10, 10]

for i, t in enumerate(times):
    data_rows.append({'base_name': 'Pukchang', 'time': t, 'cnt_fighter': pukchang_fighter[i], 'cnt_bomber': 0, 'cnt_transport': 0, 'cnt_civil': 0, 'cnt_trainer': 0})

# (4) 순안 (Sunan) - 민항/수송
# Trans: 00-08(1), 10-12(2), 14-22(1)
# Civil: 00-12(2), 14-16(1), 18-22(3)
sunan_trans = [1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1]
sunan_civil = [2, 2, 2, 2, 2, 2, 2, 1, 1, 3, 3, 3]

for i, t in enumerate(times):
    data_rows.append({'base_name': 'Sunan', 'time': t, 'cnt_fighter': 0, 'cnt_bomber': 0, 'cnt_transport': sunan_trans[i], 'cnt_civil': sunan_civil[i], 'cnt_trainer': 0})


# ---------------------------------------------------------
# 2. 정적 기지 (Static Bases) - 변화 없음 (복사)
# ---------------------------------------------------------
static_bases = [
    ('Koksan', 4, 0, 2, 0, 0),    # F4, T2
    ('Onchon', 3, 0, 0, 0, 0),    # F3
    ('Hwangju', 5, 0, 0, 0, 0),   # F5
    ('Wonsan', 2, 0, 0, 0, 0),    # F2
    ('Sondok', 0, 0, 8, 0, 0),    # T8
    ('Uiju', 0, 3, 0, 0, 0),      # B3
    ('Jangjin', 0, 0, 0, 0, 4),   # Trainer 4
    ('Toksan', 4, 0, 0, 0, 0),    # F4
    ('Kwail', 6, 0, 0, 0, 0),     # F6
    ('Orang', 2, 0, 0, 0, 0),     # F2
    ('Changjin', 0, 0, 0, 0, 0),  # Empty
    ('Hyonni', 0, 0, 0, 0, 0),    # Empty
    ('Kaechon', 3, 0, 0, 0, 0),   # F3
    ('Kangda', 0, 0, 0, 0, 0),    # Empty
    ('Kilchu', 0, 0, 2, 0, 0),    # T2 (Helicopter map to Trans)
    ('Kuup', 0, 0, 0, 0, 0),      # Empty
    ('Kumgang', 0, 0, 0, 0, 0),   # Empty
    ('Kwaksan', 0, 0, 0, 0, 0),   # Empty
    ('Kyongsong', 0, 0, 0, 0, 0), # Empty
    ('Manpo', 0, 0, 0, 0, 0),     # Empty
    ('Maengsan', 0, 0, 0, 0, 0),  # Empty
    ('Riwon', 2, 0, 0, 0, 0),     # F2
    ('Samjiyon', 1, 0, 0, 0, 0)   # F1
]

for base, f, b, tr, c, tn in static_bases:
    for t in times:
        data_rows.append({
            'base_name': base,
            'time': t,
            'cnt_fighter': f,
            'cnt_bomber': b,
            'cnt_transport': tr,
            'cnt_civil': c,
            'cnt_trainer': tn
        })

# DataFrame 생성 및 저장
df = pd.DataFrame(data_rows)
# 총 객체 수 컬럼 추가
df['total_count'] = df['cnt_fighter'] + df['cnt_bomber'] + df['cnt_transport'] + df['cnt_civil'] + df['cnt_trainer']

df.to_csv('data/scenario_data.csv', index=False)
print(f"✅ [Success] 'data/scenario_data.csv' created. (Total {len(df)} rows)")
print("   - Includes detailed timeline for Sunchon, Taetan, Pukchang, Sunan and 23 static bases.")