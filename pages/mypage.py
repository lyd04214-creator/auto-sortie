import dash
from dash import html, dcc, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from db_manager import run_query

dash.register_page(__name__, path='/mypage')

# -----------------------------------------------------------------------------
# [Data Logic]
# -----------------------------------------------------------------------------
def get_db_stats():
    """최근 7일간의 활동 통계"""
    end_date = datetime.now()
    
    # [1] X축 날짜 라벨 생성
    date_objs = [end_date - timedelta(days=i) for i in range(7)]
    date_labels = [d.strftime("%m-%d") for d in date_objs]
    date_keys = [d.strftime("%Y-%m-%d") for d in date_objs] 
    
    date_labels.reverse() 
    date_keys.reverse()
    
    daily_counts = {k: 0 for k in date_keys}

    # [2] DB 조회
    query = """
    SELECT timestamp
    FROM tb_audit_log 
    WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """
    df = run_query(query)
    
    total_count = 0
    if not df.empty:
        total_count = len(df)
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df['dt_key'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        grouped = df['dt_key'].value_counts()
        for k, v in grouped.items():
            if k in daily_counts:
                daily_counts[k] = v

    # [3] 보안 위협 카운트
    today_start = end_date.strftime("%Y-%m-%d 00:00:00")
    sec_query = """
    SELECT COUNT(*) as cnt 
    FROM tb_audit_log 
    WHERE timestamp >= :today_start
      AND (action LIKE '%%FAIL%%' OR action LIKE '%%MACRO%%' OR action LIKE '%%WARNING%%')
    """
    sec_df = run_query(sec_query, {'today_start': today_start})
    security_alerts = sec_df.iloc[0]['cnt'] if not sec_df.empty else 0

    return date_labels, list(daily_counts.values()), total_count, security_alerts

def get_audit_logs(period_hours):
    """로그 조회"""
    limit_dt = datetime.now() - timedelta(hours=int(period_hours))
    limit_str = limit_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
    SELECT timestamp, action, details, user_id 
    FROM tb_audit_log 
    WHERE timestamp >= :limit_dt
    ORDER BY timestamp DESC
    """
    df = run_query(query, {'limit_dt': limit_str})
    return df

# -----------------------------------------------------------------------------
# [Layout]
# -----------------------------------------------------------------------------
layout = dbc.Container([
    dcc.Location(id='mypage-url', refresh=True),
    dcc.Store(id='mypage-refresh-trigger'),

    # [Section 1: Profile & KPI]
    dbc.Row([
        dbc.Col([
            html.Div(className="glass-panel p-4 mt-4 mb-4", children=[
                dbc.Row([
                    # 프로필
                    dbc.Col([
                        html.Div([
                            html.Img(id='mp-profile-img', src='/assets/profile_pic.png', style={'width': '140px', 'height': '140px', 'objectFit': 'cover', 'border': '3px solid var(--accent-blue)', 'boxShadow': '0 0 20px rgba(9, 132, 227, 0.5)'}, className="rounded-circle mb-3"),
                            html.H4(id='mp-rank', className="text-neon mb-0"),
                            html.H3(id='mp-name', className="fw-bold mb-2", style={'color': 'var(--text-primary)'}),
                            html.Div(id='mp-unit', className="text-muted small mb-3"),
                            html.Div("보안 등급: II급 군사기밀", className="badge bg-danger p-2 mb-2"),
                        ], className="text-center h-100 d-flex flex-column align-items-center justify-content-center border-end border-secondary pe-4")
                    ], width=3),
                    
                    # KPI 지표
                    dbc.Col([
                        html.H5("임무 수행 종합 지표", className="text-neon mb-4 border-bottom pb-2 fw-bold"),
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.Div("주간 활동 (Total Logs)", className="small fw-bold mb-1 opacity-75"),
                                    html.H1("0", id="kpi-total-count", className="fw-bold mb-0 text-primary", style={'fontSize': '3.5rem'}),
                                    html.Div([html.Span("● Live", className="text-success fw-bold me-1"), "시스템 접속/이동/조회 합계"], className="small mt-2 text-muted")
                                ], className="kpi-card p-4 h-100 bg-light bg-opacity-10 border rounded")
                            ], width=6),
                            
                            dbc.Col([
                                html.Div([
                                    # [수정] 보안 위협 카드: 제목 + 도움말 아이콘
                                    html.Div([
                                        html.Span("보안 위협 (Today)", className="small fw-bold opacity-75"),
                                        html.I(className="fas fa-question-circle text-muted ms-2", id="macro-help-target", style={"cursor": "pointer", "fontSize": "0.9rem"})
                                    ], className="d-flex align-items-center mb-1"),
                                    
                                    # [수정] 툴팁 추가
                                    dbc.Tooltip("매크로 감지 기준: 1초 내 3회 이상 클릭/이동 시 경고 발생", target="macro-help-target", placement="top"),
                                    
                                    html.H1("0", id="kpi-security-count", className="fw-bold mb-0 text-danger", style={'fontSize': '3.5rem'}),
                                    html.Div([html.Span("⚠ Warning", className="text-danger fw-bold me-1"), "로그인 실패 및 매크로"], className="small mt-2 text-muted")
                                ], className="kpi-card p-4 h-100 bg-light bg-opacity-10 border rounded")
                            ], width=6),
                        ], className="g-3 h-75"),
                    ], width=9, className="ps-4")
                ])
            ])
        ], width=12)
    ]),

    # [Section 2: Graph & Logs]
    dbc.Row([
        # 2-1. 그래프
        dbc.Col([
            html.Div(className="glass-panel p-4 h-100", children=[
                html.H5("주간 시스템 활동 추이", className="text-neon mb-3 fw-bold"),
                dcc.Graph(id='mypage-stats-graph', config={'displayModeBar': False}, style={'height': '350px'})
            ])
        ], width=5),

        # 2-2. 로그 테이블 (4단 구성)
        dbc.Col([
            html.Div(className="glass-panel p-4 h-100", children=[
                html.Div([
                    html.H5("시스템 접근 이력", className="text-neon mb-0 fw-bold"),
                    dbc.RadioItems(
                        id="log-period-selector",
                        options=[{"label": "1일", "value": "24"}, {"label": "3일", "value": "72"}, {"label": "1주", "value": "168"}],
                        value="24",
                        className="btn-group", inputClassName="btn-check", labelClassName="btn btn-outline-secondary btn-sm", labelCheckedClassName="active"
                    )
                ], className="d-flex justify-content-between align-items-center mb-3"),
                
                html.Div(id='audit-log-table-container', style={'overflowY': 'auto', 'maxHeight': '320px'})
            ])
        ], width=7)
    ], className="mb-5")

], fluid=True)

# -----------------------------------------------------------------------------
# [Callbacks]
# -----------------------------------------------------------------------------
@callback(
    Output('mp-profile-img', 'src'), 
    Output('mp-rank', 'children'), 
    Output('mp-name', 'children'), 
    Output('mp-unit', 'children'),
    Output('mypage-stats-graph', 'figure'), 
    Output('audit-log-table-container', 'children'),
    Output('kpi-total-count', 'children'), 
    Output('kpi-security-count', 'children'),
    Input('user-session-store', 'data'), 
    Input('mypage-url', 'pathname'),
    Input('log-period-selector', 'value')
)
def update_mypage_content(session_data, pathname, period_hours):
    # 1. 프로필
    if not session_data:
        img_src, rank, name, unit = "/assets/profile_pic.png", "", "Guest", "-"
        uid = 'guest'
    else:
        uid = session_data.get('user_id')
        user_df = run_query("SELECT * FROM tb_users WHERE user_id = :uid", {'uid': uid})
        if not user_df.empty:
            row = user_df.iloc[0]
            rank, name, unit = row['rank'], row['name'], row['unit']
            img_path = row['img_path'] if row['img_path'] else 'profile_pic.png'
            img_src = f"/assets/{img_path}"
        else:
            rank, name, unit = session_data.get('rank'), session_data.get('name'), session_data.get('unit')
            img_src = "/assets/profile_pic.png"

    # 2. 통계 및 그래프
    x_labels, y_counts, total_count, security_alerts = get_db_stats()

    stats_fig = go.Figure(data=[
        go.Bar(
            x=x_labels, y=y_counts,
            marker=dict(color=y_counts, colorscale=[[0, 'rgba(9, 132, 227, 0.4)'], [1, '#00d2d3']], showscale=False),
            text=y_counts, textposition='auto'
        )
    ])
    stats_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        font=dict(family="Noto Sans KR", color='#888'), 
        margin=dict(t=20, b=30, l=30, r=20), 
        xaxis=dict(showgrid=False, type='category'), 
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', zeroline=False)
    )

    # 3. 로그 테이블
    log_df = get_audit_logs(period_hours)
    
    if log_df.empty:
        log_table = html.Div("기록 없음", className="text-muted text-center mt-5")
    else:
        rows = []
        for _, row in log_df.iterrows():
            action = str(row['action']).upper()
            details = str(row['details']) if row['details'] and str(row['details']) != 'None' else "-"
            
            row_class = ""
            if 'FAIL' in action or 'MACRO' in action or 'WARNING' in action:
                row_class = "table-danger fw-bold text-danger"
                action = f"⚠ {action}"

            rows.append(html.Tr([
                html.Td(row['timestamp'].strftime("%m-%d %H:%M:%S"), className="small text-muted"),
                html.Td(action, className="fw-bold"),
                html.Td(details, className="small text-secondary"),
                html.Td(row['user_id'], className="small")
            ], className=row_class))
        
        log_table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("일시", style={'width':'25%'}), 
                html.Th("활동 (Action)", style={'width':'25%'}), 
                html.Th("상세 (Details)", style={'width':'30%'}), 
                html.Th("사용자", style={'width':'20%'})
            ]))] + [html.Tbody(rows)], 
            striped=True, hover=True, className="table-custom align-middle", style={'fontSize': '0.85rem'}
        )

    return img_src, rank, name, unit, stats_fig, log_table, str(total_count), str(security_alerts)