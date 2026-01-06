import pandas as pd
import io
import os
import platform
import warnings
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator
from datetime import datetime, timedelta
from fpdf import FPDF
from db_manager import run_query

# 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, module="fpdf")

# -----------------------------------------------------------------------------
# [설정] 폰트 로드
# -----------------------------------------------------------------------------
def configure_font():
    font_candidates = [
        r"C:\Windows\Fonts\malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf", "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    ]
    for path in font_candidates:
        if os.path.exists(path):
            font_prop = fm.FontProperties(fname=path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False 
            return path, font_prop.get_name()
    plt.rcParams['font.family'] = 'sans-serif'
    return None, 'sans-serif'

FONT_PATH, FONT_NAME = configure_font()

# -----------------------------------------------------------------------------
# 1. 데이터 조회
# -----------------------------------------------------------------------------
def fetch_report_data(rtype, base, start, end, target_time="12:00"):
    is_comparison_mode = (base == 'ALL')
    base_cond = "AND sc.scene_name = :base" if not is_comparison_mode else ""
    params = {'base': base}

    from_clause = """
        FROM tb_scenario s 
        JOIN tb_scene sc ON s.scene_id = sc.scene_id
        LEFT JOIN tb_user_settings us ON sc.scene_name = us.base_name 
    """

    # [A. 긴급/일간] -> SCENARIO 데이터 (시간 비교)
    if rtype in ['emergency', 'daily']:
        select_clause = """
            s.timestamp, sc.scene_name, sc.name_kor,
            (s.cnt_fighter + s.cnt_bomber + s.cnt_transport) as total_count,
            COALESCE(us.risk_level, '-') as risk_degree,
            COALESCE(us.main_aircraft, '-') as main_aircraft,
            COALESCE(us.special_notes, '') as remarks
        """
        
        if rtype == 'emergency':
            dummy_date = datetime.strptime(f"2000-01-01 {target_time}:00", "%Y-%m-%d %H:%M:%S")
            start_time_str = (dummy_date - timedelta(hours=2)).strftime("%H:%M:%S")
            end_time_str = dummy_date.strftime("%H:%M:%S")
            
            params['start_time'] = start_time_str
            params['end_time'] = end_time_str
            
            query = f"""
            SELECT {select_clause} {from_clause}
            WHERE s.data_type = 'SCENARIO'
              AND TIME(s.timestamp) >= :start_time 
              AND TIME(s.timestamp) <= :end_time
              {base_cond}
            ORDER BY s.timestamp ASC
            """
            
        else: # daily
            query = f"""
            SELECT {select_clause} {from_clause}
            WHERE s.data_type = 'SCENARIO'
              {base_cond}
            ORDER BY s.timestamp ASC
            """

    # [B. 연간] -> 월별 집계
    elif rtype == 'yearly':
        if len(start) == 10: start += " 00:00:00"
        if len(end) == 10: end += " 23:59:59"
        params['start'] = start; params['end'] = end
        
        query = f"""
        SELECT DATE_FORMAT(s.timestamp, '%Y-%m') as dt_month, 
               sc.scene_name, sc.name_kor,
               MIN(s.cnt_fighter + s.cnt_bomber + s.cnt_transport) as min_count,
               ROUND(AVG(s.cnt_fighter + s.cnt_bomber + s.cnt_transport), 1) as avg_count,
               MAX(s.cnt_fighter + s.cnt_bomber + s.cnt_transport) as max_count,
               COALESCE(us.risk_level, '-') as risk_degree,
               COALESCE(us.main_aircraft, '-') as main_aircraft,
               COALESCE(us.special_notes, '') as remarks
        {from_clause}
        WHERE s.timestamp BETWEEN :start AND :end 
          {base_cond}
        GROUP BY dt_month, sc.scene_name, sc.name_kor, us.risk_level, us.main_aircraft, us.special_notes
        ORDER BY dt_month ASC
        """

    # [C. 주간/월간] -> 일자별 집계
    else:
        if len(start) == 10: start += " 00:00:00"
        if len(end) == 10: end += " 23:59:59"
        params['start'] = start; params['end'] = end

        query = f"""
        SELECT DATE_FORMAT(s.timestamp, '%Y-%m-%d') as dt_day, 
               sc.scene_name, sc.name_kor,
               MIN(s.cnt_fighter + s.cnt_bomber + s.cnt_transport) as min_count,
               ROUND(AVG(s.cnt_fighter + s.cnt_bomber + s.cnt_transport), 1) as avg_count,
               MAX(s.cnt_fighter + s.cnt_bomber + s.cnt_transport) as max_count,
               COALESCE(us.risk_level, '-') as risk_degree,
               COALESCE(us.main_aircraft, '-') as main_aircraft,
               COALESCE(us.special_notes, '') as remarks
        {from_clause}
        WHERE s.timestamp BETWEEN :start AND :end 
          {base_cond}
        GROUP BY dt_day, sc.scene_name, sc.name_kor, us.risk_level, us.main_aircraft, us.special_notes
        ORDER BY dt_day ASC
        """

    df = run_query(query, params=params)

    # 데이터 후처리
    if not df.empty:
        if 'timestamp' in df.columns:
            df['dt_obj'] = pd.to_datetime(df['timestamp'])
            df['dt_str'] = df['dt_obj'].dt.strftime('%H:%M')
            df['val_for_chart'] = df['total_count']
            
        elif 'dt_month' in df.columns: # 연간
            df['dt_obj'] = pd.to_datetime(df['dt_month'] + "-01")
            df['dt_str'] = df['dt_obj'].dt.strftime('%Y-%m')
            df['val_for_chart'] = df['max_count']
            
        elif 'dt_day' in df.columns: # 주간/월간
            df['dt_obj'] = pd.to_datetime(df['dt_day'])
            df['dt_str'] = df['dt_obj'].dt.strftime('%m-%d')
            df['val_for_chart'] = df['max_count'] 

        if rtype == 'emergency':
            df['diff_str'] = "-"; df['status_str'] = "정상"; df['is_alert'] = False
            for name, group in df.groupby('name_kor'):
                if len(group) >= 1:
                    first = group.iloc[0]['total_count']; last = group.iloc[-1]['total_count']
                    diff = last - first
                    df.loc[df['name_kor'] == name, 't1_count'] = first
                    df.loc[df['name_kor'] == name, 't2_count'] = last
                    df.loc[df['name_kor'] == name, 'diff_str'] = f"+{diff}" if diff > 0 else str(diff)
                    df.loc[df['name_kor'] == name, 'status_str'] = "이상" if diff != 0 else "정상"
                    df.loc[df['name_kor'] == name, 'is_alert'] = (diff != 0)
        else:
            df['is_alert'] = False

    return df, is_comparison_mode

# -----------------------------------------------------------------------------
# 2. 다중 차트 생성 (수정: 산점도 텍스트 폰트 적용)
# -----------------------------------------------------------------------------
def generate_multi_charts(df, rtype, is_comparison_mode):
    if df.empty: return []
    images = []
    prop = fm.FontProperties(fname=FONT_PATH) if FONT_PATH else None
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # -------------------------------------------------------------------------
    # [Chart 1] 긴급: 산점도 / 그외: 시계열
    # -------------------------------------------------------------------------
    fig1 = plt.figure(figsize=(10, 4))
    ax1 = plt.gca()
    
    if rtype == 'emergency':
        # [산점도] Scatter Plot
        df_scatter = df.drop_duplicates(subset=['name_kor']).copy()
        
        colors = []
        for i, row in df_scatter.iterrows():
            diff = row['t2_count'] - row['t1_count']
            if diff > 0: colors.append('#e74c3c') # Red
            elif diff < 0: colors.append('#3498db') # Blue
            else: colors.append('gray')
            
        plt.scatter(df_scatter['t1_count'], df_scatter['t2_count'], s=100, c=colors, alpha=0.8, zorder=3)
        
        # 대각선
        max_val = max(df_scatter['t1_count'].max(), df_scatter['t2_count'].max()) + 2
        plt.plot([0, max_val], [0, max_val], 'k--', alpha=0.3, zorder=1)
        
        plt.fill_between([0, max_val], [0, max_val], [max_val, max_val], color='#e74c3c', alpha=0.05)
        plt.fill_between([0, max_val], 0, [0, max_val], color='#3498db', alpha=0.05)

        # [수정] 텍스트 라벨에 폰트 속성 적용
        for i, row in df_scatter.iterrows():
            plt.text(
                row['t1_count'], row['t2_count'], row['name_kor'], 
                fontsize=9, fontweight='bold', ha='right', va='bottom',
                fontproperties=prop # 한글 깨짐 방지 핵심
            )

        plt.title("위협 변동 상태 분포 (Scatter Plot)", fontsize=12, fontweight='bold', fontproperties=prop)
        plt.xlabel("2시간 전 식별수", fontproperties=prop)
        plt.ylabel("현재 식별수", fontproperties=prop)
        plt.grid(True, linestyle='--')
        ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax1.yaxis.set_major_locator(MaxNLocator(integer=True))

    else:
        # [시계열]
        ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
        if is_comparison_mode:
            df_sum = df.groupby('dt_obj')['val_for_chart'].sum().reset_index()
            x = df_sum['dt_obj']; y = df_sum['val_for_chart']
            label_txt = "전 기지 식별 추이"
        else:
            x = df['dt_obj']; y = df['val_for_chart']
            label_txt = f"{df['name_kor'].iloc[0]} 식별 추이"

        plt.plot(x, y, color='#c0392b', linewidth=2, marker='o', markersize=4, label=label_txt)
        plt.fill_between(x, y, color='#e74c3c', alpha=0.1)
        
        # 값 라벨 (폰트 적용 확인)
        for i in range(len(x)):
             ax1.text(x.iloc[i], y.iloc[i], f"{int(y.iloc[i])}", fontsize=8, ha='center', va='bottom', fontweight='bold', fontproperties=prop)

        if rtype == 'daily': 
            title_suffix = "(분 단위)"
            plt.xlabel("시간", fontproperties=prop)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        elif rtype == 'yearly': 
            title_suffix = "(월별 추이)"
            plt.xlabel("월 (Month)", fontproperties=prop)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax1.xaxis.set_major_locator(mdates.MonthLocator())
            plt.xticks(rotation=45)
        else: 
            title_suffix = "(일자별 최대)"
            plt.xlabel("일자", fontproperties=prop)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            plt.xticks(rotation=0)
        
        plt.title(f"시간 흐름에 따른 식별 추이 {title_suffix}", fontsize=12, fontweight='bold', fontproperties=prop)
        plt.ylabel("식별 수량 (대)", fontproperties=prop)

    plt.tight_layout()
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='png', dpi=100)
    plt.close(fig1)
    buf1.seek(0)
    images.append(buf1)

    # -------------------------------------------------------------------------
    # [Chart 2] 기지별 비교 (Bar Chart)
    # -------------------------------------------------------------------------
    if is_comparison_mode:
        fig2 = plt.figure(figsize=(10, 5))
        ax2 = plt.gca()
        ax2.xaxis.set_major_locator(MaxNLocator(integer=True))

        if rtype == 'emergency':
            df_unique = df.drop_duplicates(subset=['name_kor']).copy()
            df_unique['abs_diff'] = abs(df_unique['t2_count'] - df_unique['t1_count'])
            df_comp = df_unique[['name_kor', 'abs_diff']].rename(columns={'abs_diff': 'value'})
            title_txt = "기지별 변동폭(절대값) 순위"
            color = '#e67e22' 
        else:
            val_col = 'val_for_chart'
            df_comp = df.groupby('name_kor')[val_col].max().reset_index()
            df_comp.columns = ['name_kor', 'value']
            title_txt = "기지별 최대 식별 수량 비교"
            color = '#7f8c8d' 

        df_comp = df_comp.sort_values('value', ascending=True)
        bases = df_comp['name_kor']
        values = df_comp['value']
        
        plt.barh(bases, values, color=color, alpha=0.8)
        plt.title(title_txt, fontsize=12, fontweight='bold', fontproperties=prop)
        plt.xlabel("수량", fontproperties=prop)
        plt.yticks(fontproperties=prop)
        
        for index, value in enumerate(values):
            if value >= 0:
                plt.text(value, index, str(int(value)), va='center', fontsize=9, fontweight='bold')

        plt.tight_layout()
        buf2 = io.BytesIO()
        plt.savefig(buf2, format='png', dpi=100)
        plt.close(fig2)
        buf2.seek(0)
        images.append(buf2)

    return images

# -----------------------------------------------------------------------------
# 3. PDF 생성 (표 데이터 변환 로직 포함)
# -----------------------------------------------------------------------------
def transform_to_summary_df(df):
    if df.empty: return df
    summary = df.groupby(['scene_name', 'name_kor']).agg(
        max_val=('max_count', 'max'),
        avg_val=('avg_count', 'mean'),
        min_val=('min_count', 'min'),
        risk_degree=('risk_degree', 'last'),
        main_aircraft=('main_aircraft', 'last'),
        remarks=('remarks', 'last')
    ).reset_index()
    
    peak_dates = []
    for _, row in summary.iterrows():
        base = row['name_kor']
        max_v = row['max_val']
        mask = (df['name_kor'] == base) & (df['max_count'] == max_v)
        try: peak_date = df[mask]['dt_str'].iloc[0]
        except: peak_date = '-'
        peak_dates.append(peak_date)
    
    summary['peak_date'] = peak_dates
    summary['avg_val'] = summary['avg_val'].round(1)
    return summary

def create_pdf_bytes(rtype, base, start, end, target_time, r_to, r_cc, comment, detail_level='brief'):
    df, is_comparison_mode = fetch_report_data(rtype, base, start, end, target_time)
    
    try:
        pdf = FPDF()
        if FONT_PATH:
            pdf.add_font('KoreanFont', '', FONT_PATH, uni=True)
            pdf.add_font('KoreanFont', 'B', FONT_PATH, uni=True)
            pdf.set_font('KoreanFont', '', 11)
        else: pdf.set_font('Arial', '', 11)

        pdf.add_page()
        pdf.set_text_color(255, 0, 0); pdf.set_font_size(14)
        pdf.cell(0, 10, "Ⅱ급 비밀 (SECRET)", 0, 1, 'C')
        pdf.set_text_color(0, 0, 0); pdf.set_font_size(16)
        
        date_info = f" ({start})" if start == end else f" ({start} ~ {end})"
        title_map = {'emergency': '긴급 작전', 'daily': '일간 상황', 'weekly': '주간 분석', 'monthly': '월간 분석', 'yearly': '연간 분석'}
        pdf.set_font('KoreanFont', 'B', 16)
        pdf.cell(0, 10, f"{title_map.get(rtype, '작전')} 보고서{date_info}", 0, 1, 'C')
        pdf.set_font('KoreanFont', '', 11)
        pdf.ln(5)

        pdf.set_font_size(10)
        pdf.cell(30, 8, "대상 기지:", 1); pdf.cell(65, 8, f" {base}", 1)
        pdf.cell(30, 8, "작성 일시:", 1); pdf.cell(65, 8, f" {datetime.now().strftime('%Y-%m-%d %H:%M')}", 1, 1)
        pdf.cell(30, 8, "수신:", 1); pdf.cell(65, 8, f" {r_to}", 1)
        pdf.cell(30, 8, "참조:", 1); pdf.cell(65, 8, f" {r_cc}", 1, 1)
        pdf.ln(5)

        charts = generate_multi_charts(df, rtype, is_comparison_mode)
        if charts:
            for buf in charts:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(buf.getvalue()); tmp_path = tmp.name
                pdf.image(tmp_path, x=10, w=190)
                os.unlink(tmp_path)
        else: pdf.cell(190, 10, "[데이터 없음]", 1, 1, 'C')
        pdf.ln(5)

        pdf.set_font('KoreanFont', 'B', 11); pdf.cell(0, 8, "1. 분석관 종합 의견", 0, 1)
        pdf.set_font('KoreanFont', '', 10); pdf.multi_cell(0, 6, f"{comment}\n", 1, 'L', False)
        pdf.ln(5)

        pdf.set_font('KoreanFont', 'B', 11); 
        if rtype in ['weekly', 'monthly', 'yearly']:
            pdf.cell(0, 8, "2. 기지별 종합 결산 (Base Summary)", 0, 1)
        else:
            pdf.cell(0, 8, "2. 상세 식별 로그", 0, 1)
            
        pdf.set_font('KoreanFont', '', 8); pdf.set_fill_color(236, 240, 241)

        if rtype == 'emergency':
            headers = [('시간', 15), ('기지명', 30), ('식별', 15), ('상태', 15), ('변동', 15), ('위험도', 20), ('주력기', 25), ('특이사항', 55)]
            cols = ['dt_str', 'name_kor', 'total_count', 'status_str', 'diff_str', 'risk_degree', 'main_aircraft', 'remarks']
            print_df = df.sort_values('timestamp').groupby('name_kor', as_index=False).tail(1) if not df.empty else df
            
        elif rtype == 'daily':
            headers = [('시간', 20), ('기지명', 35), ('식별수', 20), ('위험도', 25), ('주력기', 30), ('특이사항', 60)]
            cols = ['dt_str', 'name_kor', 'total_count', 'risk_degree', 'main_aircraft', 'remarks']
            print_df = df if (detail_level == 'detailed') else df.head(60)
            
        else:
            headers = [('기지명', 30), ('최고', 15), ('평균', 15), ('최대발생', 25), ('위험도', 20), ('주력기', 25), ('특이사항', 60)]
            cols = ['name_kor', 'max_val', 'avg_val', 'peak_date', 'risk_degree', 'main_aircraft', 'remarks']
            print_df = transform_to_summary_df(df)

        for h_name, h_w in headers: pdf.cell(h_w, 8, h_name, 1, 0, 'C', 1)
        pdf.ln()

        if not print_df.empty:
            line_height = 5
            for i in range(len(print_df)):
                row = print_df.iloc[i]
                
                max_lines = 1
                for j, (h_name, h_w) in enumerate(headers):
                    val = str(row.get(cols[j], '-'))
                    est_lines = math.ceil(len(val) / (h_w / 2.5))
                    if est_lines > max_lines: max_lines = est_lines
                row_height = max_lines * line_height

                if pdf.get_y() + row_height > 270:
                    pdf.add_page()
                    pdf.set_font('KoreanFont', '', 8)
                    for h_name, h_w in headers: pdf.cell(h_w, 8, h_name, 1, 0, 'C', 1)
                    pdf.ln()

                if row.get('is_alert', False): pdf.set_text_color(255, 0, 0)
                else: pdf.set_text_color(0, 0, 0)

                cur_x = pdf.get_x(); cur_y = pdf.get_y()
                for j, (h_name, h_w) in enumerate(headers):
                    val = str(row.get(cols[j], '-'))
                    pdf.set_xy(cur_x, cur_y)
                    pdf.multi_cell(h_w, line_height, val, border=0, align='C')
                    pdf.rect(cur_x, cur_y, h_w, row_height)
                    cur_x += h_w
                pdf.set_xy(10, cur_y + row_height)
        else: 
            pdf.cell(190, 8, "데이터 없음", 1, 1, 'C')

        logo_path = "assets/hc_logo.png"
        if os.path.exists(logo_path):
            if pdf.get_y() > 250: pdf.add_page()
            pdf.image(logo_path, x=90, y=260, w=30)
            pdf.set_y(290)
            pdf.set_font('KoreanFont', 'B', 10)
            pdf.cell(0, 5, "대한민국 합동참모본부", 0, 0, 'C')

        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        print(f"PDF Error: {e}")
        return None