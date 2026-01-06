import dash
from dash import html, dcc, Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import base64
import io
from urllib.parse import parse_qs
from datetime import datetime, timedelta
from db_manager import run_query
from ai_core import (
    get_db_image_path, run_detection_and_compare, create_figure, 
    run_classification, get_trend_data, load_image_from_path
)

dash.register_page(__name__, path='/analysis')

layout = dbc.Container([
    dcc.Location(id='analysis-url', refresh=False),
    dcc.Store(id='det-store', data={'t1': {}, 't2': {}}), 
    
    html.Div(className="glass-panel p-3 mb-3", children=[
        dbc.Row([
            dbc.Col([html.Label("1. 기지 (Base)", className="fw-bold small text-muted mb-1"), dcc.Dropdown(id='sel-base', placeholder="기지 선택", clearable=False)], width=3),
            dbc.Col([html.Label("2. 날짜 (Date)", className="fw-bold small text-muted mb-1"), dcc.DatePickerSingle(id='sel-date', display_format='YYYY-MM-DD', className="w-100")], width=3),
            dbc.Col([html.Label("3. 시간 (Target Time)", className="fw-bold small text-muted mb-1"), dcc.Dropdown(id='sel-time', placeholder="시간 선택", clearable=False)], width=3),
            dbc.Col([html.Label("Action", className="fw-bold small text-muted mb-1", style={'visibility':'hidden'}), dbc.Button([html.I(className="fas fa-search me-2"), "분석 실행"], id="btn-load", color="primary", className="w-100 fw-bold")], width=3)
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            html.Div(children=[
                html.Div([html.I(className="fas fa-history me-2"), "T1: Past Situation (T-2h)", html.Span(" (● Vanished)", className="small ms-2 opacity-75")], className="bg-dark text-white px-3 py-2 small fw-bold"),
                dcc.Loading(dcc.Graph(id="fig-t1", style={'height':'38vh'}))
            ], className="mb-3 border shadow-sm", style={'overflow':'hidden', 'borderRadius':'6px'}),
            html.Div(children=[
                html.Div([html.I(className="fas fa-satellite-dish me-2"), "T2: Current Target", html.Span(" (● New ● Static)", className="small ms-2 opacity-75")], className="bg-danger text-white px-3 py-2 small fw-bold"),
                dcc.Loading(dcc.Graph(id="fig-t2", style={'height':'38vh'}))
            ], className="border shadow-sm", style={'overflow':'hidden', 'borderRadius':'6px'})
        ], width=7),
        
        dbc.Col([
            html.Div(className="glass-panel p-3 mb-3 shadow-sm", style={'height':'38vh', 'overflowY':'auto'}, children=[
                html.H6([html.I(className="fas fa-crosshairs me-2 text-danger"), "TARGET ANALYSIS"], className="fw-bold border-bottom pb-2 mb-3"),
                html.Div(id="detail-panel", children=[
                    html.Div([html.I(className="fas fa-mouse-pointer fa-2x mb-3 text-muted"), html.Div("지도상의 객체(박스)를 선택하십시오.", className="text-muted small")], className="text-center mt-5 opacity-50")
                ])
            ]),
            html.Div(className="glass-panel p-3 shadow-sm", style={'height':'42vh'}, children=[
                 dbc.Tabs([
                    dbc.Tab(label="일간(Today)", tab_id="today", label_class_name="small fw-bold"),
                    dbc.Tab(label="주간(Week)", tab_id="week", label_class_name="small"),
                    dbc.Tab(label="월간(Month)", tab_id="month", label_class_name="small"),
                    dbc.Tab(label="연간(Year)", tab_id="year", label_class_name="small"),
                ], id="trend-tabs", active_tab="today", className="mb-2 nav-fill nav-pills custom-tabs small"),
                dcc.Graph(id="trend-chart", config={'displayModeBar': False}, style={'height': '100%'})
            ])
        ], width=5, className="ps-2")
    ], className="g-4")
], fluid=True, className="px-4 pb-4 pt-1", style={'height':'100vh', 'overflowY':'hidden', 'backgroundColor':'var(--bg-main)'})

@callback(Output('sel-base', 'options'), Output('sel-base', 'value'), Output('sel-date', 'date'), Output('sel-time', 'options'), Output('sel-time', 'value'), Input('analysis-url', 'search'), Input('sel-date', 'date'))
def init_controls(search, date_val):
    bases = []
    df = run_query("SELECT scene_name, name_kor FROM tb_scene WHERE name_kor IS NOT NULL")
    if not df.empty:
        bases = [{'label': f"{r['name_kor']} ({r['scene_name']})", 'value': r['scene_name']} for _, r in df.iterrows()]
    base = bases[0]['value'] if bases else 'Sunan'
    today = datetime.now().strftime("%Y-%m-%d")
    date = date_val if date_val else today
    all_times = [f"{h:02d}:00" for h in range(0, 24, 2)]
    options = [{'label': t, 'value': t} for t in all_times]
    time_val = "12:00"
    if search:
        try:
            qs = parse_qs(search.lstrip('?'))
            base = qs.get('base', [base])[0]
            date = qs.get('date', [date])[0]
            t_req = qs.get('time', [time_val])[0]
            if len(t_req.split(':')[0]) == 1: t_req = f"0{t_req}"
            if any(d['value'] == t_req for d in options): time_val = t_req
        except: pass
    return bases, base, date, options, time_val

@callback([Output('fig-t1', 'figure'), Output('fig-t2', 'figure'), Output('det-store', 'data')], [Input('btn-load', 'n_clicks'), Input('analysis-url', 'search')], [State('sel-base', 'value'), State('sel-date', 'date'), State('sel-time', 'value')])
def run_dual_analysis(n, search, base_st, date_st, time_st):
    trig = ctx.triggered_id
    if trig == 'analysis-url' and search:
        try:
            qs = parse_qs(search.lstrip('?'))
            base = qs.get('base', [base_st])[0]
            date = qs.get('date', [date_st])[0]
            time = qs.get('time', [time_st])[0]
            if len(time.split(':')[0]) == 1: time = f"0{time}"
        except: return no_update, no_update, no_update
    elif trig == 'btn-load' and n:
        base, date, time = base_st, date_st, time_st
    else: return no_update, no_update, no_update

    t2_path = get_db_image_path(base, date, time)
    t1_path = None
    try:
        curr_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        prev_dt = curr_dt - timedelta(hours=2)
        t1_path = get_db_image_path(base, prev_dt.strftime("%Y-%m-%d"), prev_dt.strftime("%H:%M"))
    except: pass
    
    d1, w1, h1, d2, w2, h2 = run_detection_and_compare(t1_path, t2_path)
    return create_figure(t1_path, d1), create_figure(t2_path, d2), {'t1': {'dets': d1, 'path': t1_path}, 't2': {'dets': d2, 'path': t2_path}}

@callback(Output('detail-panel', 'children'), Output('fig-t1', 'figure', allow_duplicate=True), Output('fig-t2', 'figure', allow_duplicate=True), Input('fig-t1', 'clickData'), Input('fig-t2', 'clickData'), State('det-store', 'data'), State('theme-store', 'data'), prevent_initial_call=True)
def handle_dual_click(click_t1, click_t2, store, theme):
    trigger = ctx.triggered_id
    if not store: return no_update, no_update, no_update
    target_key = 't1' if trigger == 'fig-t1' else 't2'
    click_data = click_t1 if trigger == 'fig-t1' else click_t2
    if not click_data: return no_update, no_update, no_update
    
    target_info = store.get(target_key, {})
    dets = target_info.get('dets', [])
    img_path = target_info.get('path')
    
    try:
        custom_data = click_data['points'][0]['customdata']
        if isinstance(custom_data, list): match_idx = int(custom_data[0])
        else: match_idx = int(custom_data)
    except Exception as e:
        print(f"[DEBUG] Click Data Error: {e}")
        return no_update, no_update, no_update
    
    match = next((d for d in dets if d[6] == match_idx), None)
    if not match: return no_update, no_update, no_update
    
    crop_b64, cls_res = "", {}
    try:
        im = load_image_from_path(img_path)
        if im:
            if im.mode != "RGB": im = im.convert("RGB")
            w, h = im.size
            x1, y1, x2, y2 = map(int, match[:4])
            if x2 > x1 and y2 > y1:
                crop = im.crop((x1, y1, x2, y2))
                cls_res = run_classification(crop)
                buf = io.BytesIO(); crop.save(buf, format="PNG"); crop_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[DEBUG] Detail Panel Error: {e}")
    
    is_dark = (theme == 'dark') if theme else True
    text_cls = "text-white" if is_dark else "text-dark"
    bg_panel = "rgba(255,255,255,0.05)" if is_dark else "rgba(0,0,0,0.03)"
    status_txt = match[7] if len(match) > 7 else "STATIC"
    
    # [수정 핵심] className="g-0" -> "g-3" 으로 변경하여 이미지와 글씨 사이에 간격 추가
    panel = dbc.Row([
        dbc.Col([html.Div(f"{target_key.upper()} - {status_txt}", className="text-neon small fw-bold mb-2"), html.Img(src=f"data:image/png;base64,{crop_b64}", style={'width':'100%', 'border':'1px solid #555'})], width=5),
        dbc.Col([html.H5(cls_res.get('cls_top1'), className=f"fw-bold text-danger {text_cls}"), html.Div(f"Conf: {cls_res.get('cls_conf')}", className="small fw-bold text-success mb-2"), html.Div(html.Ul(cls_res.get('cls_top5', []), className=f"small {text_cls} ps-3 mb-0"))], width=7)
    ], className="g-3 h-100 align-items-center", style={'backgroundColor': bg_panel, 'borderRadius': '8px', 'padding': '10px'})
    
    new_fig = create_figure(img_path, dets, selected_idx=match_idx)
    return panel, new_fig if target_key == 't1' else no_update, new_fig if target_key == 't2' else no_update

@callback(Output("trend-chart", "figure"), Input("trend-tabs", "active_tab"), Input("sel-base", "value"), State("theme-store", "data"))
def update_trend(active_tab, base_name, theme):
    is_dark = (theme == 'dark') if theme else True
    
    # 1. 4가지 모드 데이터 모두 가져오기
    modes = ['today', 'week', 'month', 'year']
    data_map = {}
    for m in modes:
        data_map[m] = get_trend_data(mode=m, base_name=base_name)
    
    fig = go.Figure()
    
    # 2. 색상 및 스타일 정의
    colors = {
        'today': '#FF1744',   # 빨강
        'week':  '#00E676',   # 초록
        'month': '#2979FF',   # 파랑
        'year':  '#FFD700'    # 노랑
    }
    
    dashes = {
        'today': 'solid',       
        'week':  'dash',        
        'month': 'dot',         
        'year':  'longdashdot' 
    }
    
    labels = {'today': '일간 (Today)', 'week': '주간 (Week)', 'month': '월간 (Month)', 'year': '연간 (Year)'}
    
    # 3. 그래프 그리기
    for m in modes:
        df = data_map[m]
        is_active = (m == active_tab)
        
        if is_active:
            line_width = 4
            opacity = 1.0
            mode_type = 'lines+markers+text'
            line_color = colors[m]
        else:
            line_width = 2
            opacity = 0.5 # 비활성 그래프 투명도 조정
            mode_type = 'lines'
            line_color = colors[m] 
            
        fig.add_trace(go.Scatter(
            x=df['time'], 
            y=df['count'], 
            mode=mode_type,
            name=labels[m],
            line=dict(color=line_color, width=line_width, dash=dashes[m]),
            marker=dict(size=8 if is_active else 0, color=line_color),
            opacity=opacity,
            text=[f"{v}" for v in df['count']],
            textposition="top center",
            textfont=dict(color=line_color, size=14, weight='bold')
        ))

    # 4. 레이아웃 설정 (범례 위치 수정)
    bg_color = "rgba(0,0,0,0)"
    text_color = "#ffffff" if is_dark else "#2d3436"
    
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly_white",
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color),
        # [수정] 여백 조정: 범례가 들어갈 상단 공간 확보
        margin=dict(l=10, r=10, t=50, b=20),
        
        xaxis=dict(
            showgrid=False, 
            title="TIME (00:00 ~ 22:00)", 
            color=text_color,
            fixedrange=True
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(128,128,128,0.2)',
            color=text_color, 
            zeroline=False,
            fixedrange=True
        ),
        showlegend=True,
        # [핵심 수정] 범례를 좌측 상단으로 이동
        legend=dict(
            orientation="h",      # 가로 배치
            yanchor="bottom",     # 하단 기준
            y=1.02,               # 그래프 상단 바로 위
            xanchor="left",       # 왼쪽 정렬 (기존 right에서 변경)
            x=0,                  # 왼쪽 끝에 딱 붙임
            bgcolor='rgba(0,0,0,0)' # 배경 투명
        ),
        hovermode="x unified"
    )
    return fig