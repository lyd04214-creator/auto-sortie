import pandas as pd
import io

# 사용자가 제공한 데이터 (문자열로 가정, 파일이라면 pd.read_csv('파일경로') 사용)
csv_data = """base_name,time,cnt_fighter,cnt_bomber,cnt_transport,cnt_civil,total_count,img_path
...(위의 데이터를 여기에 넣거나, CSV 파일을 로드하세요)...
"""

# 1. 데이터 로드 (파일인 경우 pd.read_csv("파일명.csv") 사용)
# df = pd.read_csv(io.StringIO(csv_data)) # 테스트용
# df = pd.read_csv("scenario_data.csv") # 실제 파일 사용 시

# -----------------------------------------------------------
# [핵심 로직] 시간(00~22)을 2로 나누고 1을 더해 인덱스(1~12) 생성
# -----------------------------------------------------------
def fix_img_path(row):
    # 1. 기지명 소문자로 변환 (예: Sunchon -> sunchon)
    base = row['base_name'].lower()
    
    # 2. 시간 추출 (예: "00:00" -> 0, "22:00" -> 22)
    hour = int(row['time'].split(':')[0])
    
    # 3. 인덱스 계산 공식: (시간 / 2) + 1
    # 00시 -> 0/2 + 1 = 1 (t1)
    # 02시 -> 2/2 + 1 = 2 (t2)
    # ...
    # 22시 -> 22/2 + 1 = 12 (t12)
    idx = (hour // 2) + 1
    
    # 4. 최종 파일명 생성
    return f"{base}_t{idx}.png"

# 데이터프레임에 적용
df['img_path'] = df.apply(fix_img_path, axis=1)

# 결과 확인 (상위 20개 출력)
print(df[['base_name', 'time', 'img_path']].head(24))

# CSV로 저장
# df.to_csv("scenario_data_fixed_path.csv", index=False)