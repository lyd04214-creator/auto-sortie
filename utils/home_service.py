import pandas as pd
from datetime import datetime
from db_manager import run_query

# ---------------------------------------------------------
# [설정] 시스템이 인식하는 '오늘' (매일매일 여기가 '오늘'이 됩니다)
# ---------------------------------------------------------

def fetch_daily_data(target_date_str):
    today_str = datetime.now().strftime('%Y-%m-%d')
    """
    [날짜별 데이터 조회 분기]
    - 오늘 날짜 요청 시 -> fetch_live_scenarios (날짜 변조해서 가져옴)
    - 과거 날짜 요청 시 -> fetch_past_history (그냥 있는 그대로 가져옴)
    """
    if target_date_str == today_str:
        return fetch_live_scenarios()
    else:
        # 특정 과거 날짜의 이력 조회
        try:
            sql = f"""
                SELECT 
                    s.*, 
                    c.scene_name as base_name, 
                    c.name_kor, 
                    c.lat, 
                    c.lon
                FROM TB_SCENARIO s
                JOIN TB_SCENE c ON s.scene_id = c.scene_id
                WHERE s.data_type = 'HISTORY'
                  AND DATE(s.timestamp) = '{target_date_str}'
            """
            df = run_query(sql)
            if not df.empty:
                return df.to_dict('records')
            return []
        except Exception as e:
            print(f"[Service Error] Past Date Fetch: {e}")
            return []

def fetch_live_scenarios():
    """
    [오늘(시나리오) 데이터 조회]
    핵심: DB에 저장된 날짜를 무시하고, 무조건 today_str 날짜로 덮어씌움.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        # [핵심 SQL] TIMESTAMP(CONCAT(...))를 사용하여 날짜를 강제 변경
        sql = f"""
            SELECT 
                s.data_id, s.scene_id, s.status, 
                s.cnt_fighter, s.cnt_bomber, s.cnt_transport, s.cnt_civil, s.cnt_trainer,
                s.data_type, s.weather, s.wind_speed, s.moon_phase,
                TIMESTAMP(CONCAT('{today_str} ', TIME(s.timestamp))) as timestamp,
                c.scene_name as base_name, 
                c.name_kor, 
                c.lat, 
                c.lon
            FROM TB_SCENARIO s
            JOIN TB_SCENE c ON s.scene_id = c.scene_id
            WHERE s.data_type = 'SCENARIO'
            ORDER BY s.timestamp DESC
        """
        df = run_query(sql)
        if not df.empty:
            return df.to_dict('records')
        return []
    except Exception as e:
        print(f"[Service Error] Scenario Fetch: {e}")
        return []

def fetch_past_history_range(hours=72):
    """
    [우측 로그용 과거 데이터 조회]
    수정사항: Python 레벨의 '72시간 제한' 필터링을 제거하여, 
    데이터가 띄엄띄엄 있어도 SQL이 가져온 최근 1000개를 무조건 보여줌.
    """
    # 1. 현재 서버 날짜 가져오기 (예: 2026-01-07)
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # 오늘 자정(00:00:00)을 기준으로 설정
        cutoff_str = f"{today_str} 00:00:00"
        
        # 2. SQL: 오늘 이전의 데이터만 가져와라 (미래 데이터인 1월 8일~12일 등은 제외됨)
        sql = f"""
            SELECT 
                s.*, 
                c.scene_name as base_name, 
                c.name_kor
            FROM TB_SCENARIO s
            JOIN TB_SCENE c ON s.scene_id = c.scene_id
            WHERE s.data_type = 'HISTORY'
              AND s.timestamp < '{cutoff_str}'
            ORDER BY s.timestamp DESC
            LIMIT 1000
        """
        df = run_query(sql)
        
        if not df.empty:
            cols = ['cnt_fighter', 'cnt_bomber', 'cnt_transport', 'cnt_civil', 'cnt_trainer']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            df['total_count'] = df[cols].sum(axis=1).astype(int)
            
            return df.to_dict('records')
            
        return []

    except Exception as e:
        print(f"[Service Error] History Range Fetch: {e}")
        return []

def process_scenario_data(scen_data):
    """
    [데이터 전처리]
    """
    df = pd.DataFrame(scen_data)
    if df.empty:
        return pd.DataFrame()

    if 'timestamp' in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['dt'].dt.hour
        
        cols = ['cnt_fighter', 'cnt_bomber', 'cnt_transport', 'cnt_civil', 'cnt_trainer']
        exist_cols = [c for c in cols if c in df.columns]
        
        if exist_cols:
            df[exist_cols] = df[exist_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            df['total_count'] = df[exist_cols].sum(axis=1).astype(int)
        else:
            df['total_count'] = 0
            
    return df