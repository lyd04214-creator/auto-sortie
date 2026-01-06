import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# 1. 폴더 생성
if not os.path.exists('data'):
    os.makedirs('data')

# ---------------------------------------------------------
# 2. 로그인 사용자 데이터 (users.csv) - 강재현 단독
# ---------------------------------------------------------
users_data = {
    'service_number': ['25-10301'],
    'password': ['1234'],
    'name': ['Kang Jae-hyun'],
    'rank': ['Lieutenant'],
    'unit': ['ROKAF 10th Fighter Wing, Intel Div.'],
    'clearance': ['Level 3 (Confidential)'],
    # 중요: 웹 서버에서는 /assets/파일명 으로 접근해야 합니다.
    'img_path': ['/assets/profile_pic.png'] 
}
pd.DataFrame(users_data).to_csv('data/users.csv', index=False)
print("✅ [Success] 'data/users.csv' created (User: Kang Jae-hyun).")

# ---------------------------------------------------------
# 3. 기지별 1년치 통계 데이터 (historical_stats.csv)
# ---------------------------------------------------------
bases = [
    'Sunchon', 'Pukchang', 'Taetan', 'Sunan', 'Onchon', 'Hwangju', 'Koksan',
    'Wonsan', 'Sondok', 'Uiju', 'Jangjin', 'Toksan', 'Kwail', 'Orang', 'Yonpo',
    'Kaechon', 'Panghyon', 'Hwangsuwon', 'Taechon', 'Hyesan', 'Samjiyon', 'Kilchu',
    'Kowon', 'Nuchon', 'Hyonli', 'Samjangcol'
]

end_date = datetime(2025, 12, 24)
start_date = end_date - timedelta(days=365)
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

all_data = []
np.random.seed(42)

for base in bases:
    if base in ['Sunchon', 'Pukchang', 'Taetan', 'Sunan']:
        avg_activity = 10
        variability = 5
    else:
        avg_activity = 2
        variability = 2

    for d in date_range:
        count = int(np.random.normal(avg_activity, variability))
        count = max(0, count)
        if d.weekday() >= 5: count = int(count * 0.5)
        if d.day == 15: count += np.random.randint(5, 10)
        
        status = 'WARNING' if count > avg_activity * 2 + 3 else 'STABLE'

        all_data.append({
            'date': d.strftime('%Y-%m-%d'),
            'base_name': base,
            'total_count': count,
            'status': status
        })

pd.DataFrame(all_data).to_csv('data/historical_stats.csv', index=False)
print("✅ [Success] 'data/historical_stats.csv' created.")