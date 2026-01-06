import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
import pymysql
import certifi

# [1] DB 접속 정보
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "gateway01.ap-northeast-1.prod.aws.tidbcloud.com"), # 기본값은 로컬 테스트용으로 남겨둬도 됨
    "port": int(os.getenv("DB_PORT", 4000)),
    "user": os.getenv("DB_USER", "2nCr8H4UyD3qHYg.root"),
    "password": os.getenv("DB_PASSWORD", "6MF8kQVxjzU411UG"), # 실제 배포 시엔 Render 설정에서 불러옴
    "database": os.getenv("DB_NAME", "test") 
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_IMG_DIR = os.path.join(BASE_DIR, 'assets', 'images')

# [2] DB 엔진 최적화
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

ENGINE = create_engine(
    DATABASE_URL, 
    connect_args={"ssl": {"ca": certifi.where()}, "connect_timeout": 10},
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20
)

# [3] 공통 함수 정의

def run_query(query_str, params=None):
    """
    쿼리 실행 함수 (SELECT 및 INSERT/UPDATE/DELETE 자동 분기)
    """
    try:
        # 공백 제거 및 대문자 변환 후 'SELECT'로 시작하는지 확인
        qs = query_str.strip().upper()
        
        with ENGINE.connect() as conn:
            # [A] SELECT 문일 경우 -> 데이터 반환
            if qs.startswith('SELECT'):
                df = pd.read_sql(text(query_str), conn, params=params)
                return df
            
            # [B] INSERT, UPDATE, DELETE 문일 경우 -> 실행만 하고 커밋
            else:
                conn.execute(text(query_str), params if params else {})
                conn.commit()
                return pd.DataFrame() # 빈 데이터프레임 반환 (에러 방지)
                
    except Exception as e:
        print(f"[DB Query Error] {e}")
        return pd.DataFrame()

def execute_query(query_str, params=None):
    """INSERT/UPDATE/DELETE 전용 (run_query로 통합 가능하나 호환성 유지)"""
    return run_query(query_str, params)

def get_weather_info(time_str, base_name='Sunan'):
    query = """
    SELECT s.weather, s.wind_speed, s.moon_phase
    FROM tb_scenario s
    JOIN tb_scene sc ON s.scene_id = sc.scene_id
    WHERE DATE_FORMAT(s.timestamp, '%H:00') = :tm 
      AND sc.scene_name = :bn 
      AND s.data_type = 'SCENARIO' 
    LIMIT 1
    """
    df = run_query(query, params={'tm': time_str, 'bn': base_name})
    if not df.empty:
        r = df.iloc[0]
        return {
            'weather': r['weather'] if r['weather'] else 'Clear',
            'wind': r['wind_speed'] if r['wind_speed'] is not None else 0,
            'moon': r['moon_phase'] if r['moon_phase'] is not None else 0
        }
    return {'weather': 'Clear', 'wind': 0, 'moon': 0}

def log_action(user_id, action, details=None):
    try:
        # 1. 쿼리문에 :det 가 있는지 확인
        sql = """
            INSERT INTO tb_audit_log (user_id, action, details, timestamp)
            VALUES (:uid, :act, :det, NOW())
        """
        # 2. 파라미터 딕셔너리에 'det'가 있는지 확인
        params = {
            'uid': user_id, 
            'act': action,
            'det': details  
        }
        run_query(sql, params) 
        
    except Exception as e:
        print(f"[Log Error] {e}")

def load_user_settings(user_id):
    query = """
        SELECT base_name, risk_level, main_aircraft, special_notes 
        FROM tb_user_settings 
        WHERE user_id = :uid
    """
    df = run_query(query, params={'uid': user_id})
    
    settings = {}
    if not df.empty:
        for _, row in df.iterrows():
            settings[row['base_name']] = {
                'risk_level': row.get('risk_level', 'G'), 
                'main_aircraft': row.get('main_aircraft', ""), 
                'special_notes': row.get('special_notes', "") 
            }
    return settings

def save_user_settings(user_id, base_name, risk_level, main_aircraft=None, special_notes=None):
    query = """
    INSERT INTO tb_user_settings (user_id, base_name, risk_level, main_aircraft, special_notes, updated_at)
    VALUES (:uid, :base, :risk, :aircraft, :notes, :now)
    ON DUPLICATE KEY UPDATE 
        risk_level = :risk,
        main_aircraft = :aircraft,
        special_notes = :notes,
        updated_at = :now
    """
    try:
        params = {
            'uid': user_id, 
            'base': base_name, 
            'risk': risk_level, 
            'aircraft': main_aircraft, 
            'notes': special_notes,
            'now': datetime.now()
        }
        run_query(query, params)
        return True
    except Exception as e:
        print(f"[DB Save Error] {e}")
        return False

def get_safe_image_path(img_name):
    if not img_name: return None
    path = os.path.join(ASSETS_IMG_DIR, str(img_name))
    if os.path.exists(path): return path
    return None

# [호환성 패치] (ID, Action) 순서를 (Action, ID)로 호출하는 구버전 코드 대응
# login.py에서 log_action("LOGIN_SUCCESS", user_id) 처럼 호출할 때 에러 방지
def log_user_action(action, user_id):
    return log_action(user_id, action)