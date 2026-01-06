import pandas as pd
import json
import os
import random

# --- [지능형 경로 설정] ---
# 현재 파일(init_data.py)의 위치를 확인
current_dir = os.path.dirname(os.path.abspath(__file__))

# 만약 현재 위치가 'data' 폴더 안이라면 -> 부모 폴더(프로젝트 루트)를 BASE_DIR로 설정
if os.path.basename(current_dir) == 'data':
    BASE_DIR = os.path.dirname(current_dir)
else:
    BASE_DIR = current_dir

# 이제 경로는 무조건 프로젝트 루트 기준입니다.
DATA_DIR = os.path.join(BASE_DIR, 'data')
SCEN_PATH = os.path.join(DATA_DIR, 'scenario_data.csv')
SETTING_PATH = os.path.join(DATA_DIR, 'user_settings.json')
BASES_PATH = os.path.join(DATA_DIR, 'bases.csv')

def update_scenario_data():
    """시나리오 데이터에 기상 정보를 추가합니다."""
    print(f"📂 데이터 경로 확인: {DATA_DIR}")
    
    if not os.path.exists(SCEN_PATH):
        print(f"❌ 파일을 찾을 수 없습니다: {SCEN_PATH}")
        return

    df = pd.read_csv(SCEN_PATH)
    
    if 'weather' in df.columns:
        print("✅ 이미 날씨 데이터가 존재합니다. (패스)")
    else:
        print("🛠️ 날씨 데이터 생성 중...")
        conditions = ['Clear', 'Clear', 'Cloudy', 'Cloudy', 'Rain', 'Cloudy']
        
        weather_list = []
        wind_list = []
        moon_list = []
        
        for i, row in df.iterrows():
            try:
                h = int(str(row['time']).split(':')[0])
            except:
                h = 12 
            
            w_idx = (h // 4) % len(conditions)
            weather = conditions[w_idx]
            wind = round(random.uniform(2.5, 8.5), 1)
            
            if h >= 18 or h <= 6:
                moon = 78 
            else:
                moon = 0
                
            weather_list.append(weather)
            wind_list.append(wind)
            moon_list.append(moon)
            
        df['weather'] = weather_list
        df['wind_speed'] = wind_list
        df['moon_phase'] = moon_list
        
        df.to_csv(SCEN_PATH, index=False, encoding='utf-8')
        print(f"✅ scenario_data.csv 업데이트 완료!")

def create_default_settings():
    """사용자 설정 초기값 JSON 생성"""
    
    bases = ['Sunan', 'Pukchang'] 
    if os.path.exists(BASES_PATH):
        try:
            df_b = pd.read_csv(BASES_PATH)
            df_b.columns = [c.strip().lower() for c in df_b.columns]
            if 'base_name' in df_b.columns:
                bases = df_b['base_name'].tolist()
        except Exception as e:
            print(f"⚠️ 기지 목록 로드 실패: {e}")
        
    default_config = {}
    
    for base in bases:
        default_config[base] = {
            "risk": "G", 
            "primary_aircraft": "MIG-29 (Fulcrum)",
            "risk_threshold": "Manual"
        }
        
    full_data = {"admin": default_config}
    
    with open(SETTING_PATH, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, indent=4, ensure_ascii=False)
    
    print(f"✅ user_settings.json 생성 완료!")

if __name__ == "__main__":
    print(f"🚀 초기화 스크립트 시작 (Root 감지: {BASE_DIR})")
    update_scenario_data()
    create_default_settings()
    print("✨ 모든 데이터 준비 완료.")