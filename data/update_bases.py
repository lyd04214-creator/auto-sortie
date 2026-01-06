import pandas as pd
import os

def update_bases_file():
    print("🔄 [System] 기지 정보(bases.csv) 업데이트를 시작합니다...")
    
    # 23개 확정 리스트 및 메타데이터 (좌표는 기존 데이터 기반 매핑)
    # 괄호가 포함된 명칭은 그대로 사용합니다.
    bases_data = [
        # Group A (핵심)
        {'base_name': 'Sunchon', 'name_kor': '순천', 'lat': 39.4125, 'lon': 125.8903, 'type': 'Airbase'},
        {'base_name': 'Pukchang', 'name_kor': '북창', 'lat': 39.5050, 'lon': 125.9640, 'type': 'Airbase'},
        {'base_name': 'Taetan', 'name_kor': '태탄', 'lat': 38.1311, 'lon': 125.2458, 'type': 'Airbase'},
        {'base_name': 'Sunan (Pyongyang)', 'name_kor': '순안(평양)', 'lat': 39.2005, 'lon': 125.6705, 'type': 'Airport'}, # 명칭 변경
        
        # Group B (기타)
        {'base_name': 'Onchon', 'name_kor': '온천', 'lat': 38.8920, 'lon': 125.2405, 'type': 'Airbase'},
        {'base_name': 'Hwangju', 'name_kor': '황주', 'lat': 38.6545, 'lon': 125.7905, 'type': 'Airbase'},
        {'base_name': 'Koksan', 'name_kor': '곡산', 'lat': 38.6902, 'lon': 126.6060, 'type': 'Airbase'},
        {'base_name': 'Wonsan (Kalma)', 'name_kor': '원산(갈마)', 'lat': 39.1670, 'lon': 127.4820, 'type': 'Naval'}, # 명칭 변경
        {'base_name': 'Sondok', 'name_kor': '선덕', 'lat': 39.7435, 'lon': 127.4765, 'type': 'Airbase'},
        {'base_name': 'Uiju', 'name_kor': '의주', 'lat': 40.1505, 'lon': 124.4170, 'type': 'Airbase'},
        {'base_name': 'Jangjin', 'name_kor': '장진', 'lat': 40.3636, 'lon': 127.2514, 'type': 'Airbase'},
        {'base_name': 'Toksan', 'name_kor': '덕산', 'lat': 39.9950, 'lon': 127.6100, 'type': 'Airbase'},
        {'base_name': 'Kwail', 'name_kor': '과일', 'lat': 38.4233, 'lon': 125.0200, 'type': 'Airbase'},
        {'base_name': 'Orang', 'name_kor': '어랑', 'lat': 41.4286, 'lon': 129.6469, 'type': 'Airbase'},
        {'base_name': 'Kaechon', 'name_kor': '개천', 'lat': 39.7520, 'lon': 125.9030, 'type': 'Airbase'},
        {'base_name': 'Panghyon', 'name_kor': '방현', 'lat': 39.9280, 'lon': 125.2070, 'type': 'Airbase'},
        {'base_name': 'Hwangsuwon', 'name_kor': '황수원', 'lat': 40.6750, 'lon': 128.1500, 'type': 'Airbase'},
        {'base_name': 'Taechon', 'name_kor': '태천', 'lat': 39.9050, 'lon': 125.4900, 'type': 'Airbase'},
        {'base_name': 'Hyesan', 'name_kor': '혜산', 'lat': 41.3850, 'lon': 128.1400, 'type': 'Airbase'},
        {'base_name': 'Samjiyon', 'name_kor': '삼지연', 'lat': 41.9050, 'lon': 128.4100, 'type': 'Airbase'},
        {'base_name': 'Kowon', 'name_kor': '고원', 'lat': 39.4350, 'lon': 127.3900, 'type': 'Airbase'},
        {'base_name': 'Nuchon', 'name_kor': '누천', 'lat': 38.2350, 'lon': 125.9800, 'type': 'Airbase'},
        {'base_name': 'Hyonli', 'name_kor': '현리', 'lat': 38.6100, 'lon': 127.4600, 'type': 'Airbase'},
    ]

    df = pd.DataFrame(bases_data)
    
    # 디렉토리 확인
    if not os.path.exists('data'):
        os.makedirs('data')
        
    df.to_csv('data/bases.csv', index=False, encoding='utf-8-sig')
    print(f"✅ 'data/bases.csv' 업데이트 완료! (총 {len(df)}개 기지)")
    print(df['base_name'].tolist())

if __name__ == "__main__":
    update_bases_file()