import dash
from dash import html, dcc, Input, Output, State, callback, ctx, no_update, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

# [모듈 임포트]
from db_manager import get_weather_info, load_user_settings, run_query
from utils.home_service import fetch_daily_data, fetch_past_history_range, process_scenario_data, SIMULATION_TODAY

dash.register_page(__name__, path='/home', order=1)

PIN_SIZE_NORMAL = 15
PIN_SIZE_ALERT = 15
PIN_SIZE_SELECTED_OUTER = 30 
PIN_SIZE_SELECTED_MID = 15   

# -----------------------------------------------------------------------------
# [레이아웃] - 상단 고정(No Scroll), 하단 스크롤, 비율 45:55 유지
# -----------------------------------------------------------------------------
layout = dbc.Container([
    dcc.Store(id='scenario-store'),         
    dcc.Store(id='history-store'),          
    dcc.Store(id='locked-target-store', storage_type='session'), 
    dcc.Store(id='bookmark-store', storage_type='local', data=[]),
    dcc.Store(id='local-settings', storage_type='local'), 

    dcc.Interval(id='clock-interval', interval=1000, n_intervals=0), 
    dcc.Interval(id='data-interval', interval=10000, n_intervals=0), 

    # [전체 높이 100vh]
    dbc.Row([
        # [Left] 컨트롤 & 리스트
        dbc.Col([
            # 1. 상단: 타임 컨트롤러 (높이 45%)
            # [수정] overflow: 'hidden' -> 'visible'로 변경하고 zIndex 추가하여 달력 짤림 방지
            html.Div(className="glass-panel p-3 mb-2", style={'height': '45%', 'overflow': 'visible', 'zIndex': '10', 'position': 'relative'}, children=[
                html.Div([html.Span(className="live-dot"), html.Span("LIVE OPs", className="fw-bold text-danger small")], className="mb-1"),
                dbc.Row([dbc.Col(html.Div(id="js-live-clock", className="tactical-clock-box"), width=7), dbc.Col(html.Div(id="weather-widget", className="text-end small fw-bold"), width=5)], className="align-items-center mb-3 border-bottom border-secondary pb-2"),
                html.Label("작전 일자", className="text-muted small mb-1 fw-bold"),
                
                # [옵션] 달력이 너무 크면 with_portal=True 속성을 추가하여 아예 모달처럼 띄울 수도 있습니다.
                dcc.DatePickerSingle(
                    id='date-picker', 
                    date=SIMULATION_TODAY, 
                    display_format='YYYY-MM-DD', 
                    className="w-100 mb-3",
                    style={'zIndex': '100'} # 달력 자체 우선순위
                ),
                
                html.Div([html.Span("작전 시간", className="text-muted small fw-bold"), html.Span(id="slider-status-text", className="small fw-bold float-end")], className="mb-1"),
                dcc.Slider(id='time-slider', min=0, max=22, step=2, value=None, marks={i: f'{i:02d}' for i in range(0, 24, 2)})
            ]),
            
            # 2. 하단: 리스트 (나머지 높이 채움 / 내부 스크롤 허용)
            html.Div(className="glass-panel p-3", style={'height':'calc(55% - 0.5rem)'}, children=[
                dbc.Tabs([
                    dbc.Tab(label="이상징후", tab_id="tab-alert", label_class_name="small fw-bold text-danger"),
                    dbc.Tab(label="전체기지", tab_id="tab-all", label_class_name="small"),
                    dbc.Tab(label="즐겨찾기", tab_id="tab-fav", label_class_name="small"),
                ], id="status-tabs", active_tab="tab-alert", className="mb-2 nav-fill custom-tabs"),
                # 리스트 영역 스크롤 (overflowY: auto)
                html.Div(id="base-list", className="mt-2", style={'height':'calc(100% - 40px)', 'overflowY':'auto', 'paddingRight':'5px'})
            ])
        ], width=3, style={'height':'90vh'}),
        
        # [Center] 지도
        dbc.Col([
            html.Div(className="glass-panel p-0 h-100", style={'position':'relative', 'overflow':'hidden'}, children=[
                dcc.Graph(id="ops-map", style={'height':'100%', 'width':'100%'}, config={'displayModeBar':False}),
                html.Div([
                    html.Div([html.Span("● ", style={'color':'#FF1744'}), "ALERT (위협)"], className="fw-bold mb-1"),
                    html.Div([html.Span("● ", style={'color':'#535C58'}), "STABLE (정상)"], className="fw-bold")
                ], style={'position': 'absolute', 'top': '15px', 'right': '15px', 'background': 'rgba(0,0,0,0.8)', 'padding': '12px', 'borderRadius': '8px', 'color': 'white', 'fontSize':'0.8rem'}),
                html.Div(id="map-popup-layer", style={'display': 'none'}, children=[
                    html.Div(style={
                        'position': 'absolute', 'top': '20px', 'left': '20px', 'width': '300px', 'backgroundColor': 'rgba(0, 15, 30, 0.95)',
                        'color': 'white', 'border': '1px solid #00d2d3', 'borderLeft': '5px solid #00d2d3', 'borderRadius': '4px', 'padding': '15px', 'zIndex': '1000',
                        'boxShadow': '0 5px 15px rgba(0,0,0,0.5)', 'backdropFilter': 'blur(5px)', 'textAlign': 'left'
                    }, children=[
                        html.Button("×", id="btn-close-popup", style={'position': 'absolute', 'top': '0px', 'right': '8px', 'background': 'none', 'border': 'none', 'color': '#00d2d3', 'fontSize': '28px', 'cursor': 'pointer', 'lineHeight': '1'}),
                        html.H5(id="popup-title", className="fw-bold mb-2 text-white"), 
                        html.Img(id="popup-image", style={'width':'100%', 'height':'160px', 'objectFit':'cover', 'backgroundColor':'#000', 'marginBottom':'10px'}),
                        html.Div(id="popup-desc", style={'color': '#dddddd'})
                    ])
                ])
            ])
        ], width=6, style={'height':'90vh'}),
        
        # [Right] 패널 & 로그
        dbc.Col([
            # 1. 상단: 상세 분석 패널 (높이 45% / 스크롤 없음 / 내용 넘치면 hidden)
            html.Div(id="target-action-panel", className="glass-panel p-3 mb-2", style={'height':'45%', 'overflow':'hidden'}),
            
            # 2. 하단: 로그 (나머지 높이 채움 / 내부 스크롤 허용)
            html.Div(className="glass-panel p-3", style={'height':'calc(55% - 0.5rem)'}, children=[
                html.Div([
                    html.H6([html.I(className="fas fa-history me-2"), "ALERT HISTORY"], className="text-neon fw-bold mb-0"),
                    dbc.RadioItems(
                        id="history-period-selector",
                        options=[{"label": "오늘", "value": "24"}, {"label": "3일", "value": "72"}, {"label": "1주", "value": "168"}, {"label": "1달", "value": "720"}],
                        value="24",
                        className="btn-group w-100", inputClassName="btn-check", labelClassName="btn btn-outline-secondary btn-sm py-0 px-1 flex-fill", labelCheckedClassName="active",
                        style={'fontSize':'0.8rem'}
                    )
                ], className="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2"),
                # 로그 영역 스크롤 (overflowY: auto)
                html.Div(id="alert-log-box", style={'overflowY':'auto', 'height':'calc(100% - 40px)'})
            ])
        ], width=3, style={'height':'90vh'})
    ], className="g-3 h-100")

], fluid=True, style={'height':'100vh', 'overflow':'hidden', 'backgroundColor':'var(--bg-main)', 'padding':'2px'})


# -----------------------------------------------------------------------------
# [Callbacks]
# -----------------------------------------------------------------------------

@callback(Output('scenario-store', 'data'), Output('history-store', 'data'), Input('data-interval', 'n_intervals'), Input('date-picker', 'date'), Input('history-period-selector', 'value'))
def update_data(n, date_val, period):
    d_str = date_val if isinstance(date_val, str) else date_val.strftime('%Y-%m-%d')
    daily_data = fetch_daily_data(d_str)
    hours_int = int(period) if period else 24
    past_history_data = fetch_past_history_range(hours=hours_int)
    return daily_data, past_history_data

@callback(Output('js-live-clock', 'children'), Output('weather-widget', 'children'), Output('time-slider', 'max'), Output('time-slider', 'marks'), Output('time-slider', 'value'), Input('clock-interval', 'n_intervals'), State('time-slider', 'value'))
def update_clock(n, slider_val):
    now = datetime.now()
    target_val = now.hour - (now.hour % 2)
    clock = [html.Div(now.strftime("%Y-%m-%d"), className="small text-muted"), html.Div(now.strftime("%H:%M:%S"), className="fs-3 fw-bold")]
    try: w = get_weather_info(f"{target_val:02d}:00")
    except: w = {'weather':'-', 'wind':0}
    weather = [html.Div([html.I(className="fas fa-cloud me-1"), w.get('weather','-')]), html.Div([html.I(className="fas fa-wind me-1"), f"{w.get('wind',0)}m/s"]), html.Div([html.I(className="far fa-moon me-1"), "45%"], className="small text-muted")]
    return clock, weather, 22, {i: f'{i:02d}' for i in range(0, 24, 2)}, (target_val if slider_val is None else no_update)

@callback(Output("locked-target-store", "data"), Input("ops-map", "clickData"), Input({'type': 'target-click-area', 'index': ALL}, 'n_clicks'), State("locked-target-store", "data"))
def interact(map_click, list_click, curr_locked):
    trigger = ctx.triggered_id
    if not trigger: return curr_locked
    if trigger == "ops-map" and map_click: return map_click['points'][0]['customdata']
    if isinstance(trigger, dict) and trigger['type'] == 'target-click-area': return trigger['index']
    return curr_locked

@callback(Output("map-popup-layer", "style"), Output("popup-title", "children"), Output("popup-image", "src"), Output("popup-desc", "children"), Input("locked-target-store", "data"), Input("btn-close-popup", "n_clicks"), State("scenario-store", "data"), State("time-slider", "value"), State("local-settings", "data"))
def toggle_map_popup(locked_code, close_btn, scen_data, slider_val, local_settings):
    trigger = ctx.triggered_id
    if not locked_code or trigger == "btn-close-popup": return {'display': 'none'}, "", "", ""
    k_name = locked_code; lat_val = 0; lon_val = 0
    if scen_data:
        df = pd.DataFrame(scen_data)
        if not df.empty and 'base_name' in df.columns:
            row = df[df['base_name'] == locked_code]
            if not row.empty: k_name = row.iloc[0]['name_kor']; lat_val = row.iloc[0]['lat']; lon_val = row.iloc[0]['lon']
    
    is_secure = local_settings.get('secure_mode', False) if local_settings else False
    if is_secure: lat_str = f"LAT: N **.****"; lon_str = f"LON: E ***.****"
    else: lat_str = f"LAT: {lat_val:.4f}"; lon_str = f"LON: {lon_val:.4f}"

    current_hour = slider_val if slider_val is not None else 12
    time_idx = int((current_hour / 2) + 1)
    base_lower = str(locked_code).lower()
    img_path = f"/assets/images/{base_lower}_t{time_idx}.png" 
    desc = html.Div([html.Div(f"CODE: {locked_code} | TIME: {current_hour:02d}:00", className="fw-bold", style={'color': '#00d2d3'}), html.Div(f"{lat_str}  |  {lon_str}", className="small", style={'color': 'rgba(255, 255, 255, 0.7)'})])
    return {'display': 'block'}, k_name, img_path, desc

# [핵심 수정] 우측 패널 렌더링 - 텍스트 색상 자동 전환 로직 추가
@callback(Output("target-action-panel", "children"), Input("locked-target-store", "data"), State("date-picker", "date"), State("time-slider", "value"), State("theme-store", "data"), State("scenario-store", "data"), State("local-settings", "data"), State("user-session-store", "data"))
def render_panel(locked, d_val, t_val, theme, data, local_settings, session):
    if not locked: return html.Div([html.I(className="fas fa-crosshairs fa-2x mb-3"), html.Br(), "지도에서 기지를 선택하십시오."], className="text-center text-muted mt-5 pt-5")
    
    k_name = locked; lat_val = 0; lon_val = 0
    if data:
        df = pd.DataFrame(data)
        if not df.empty and 'base_name' in df.columns:
            row = df[df['base_name'] == locked]
            if not row.empty: k_name = row.iloc[0]['name_kor']; lat_val = row.iloc[0]['lat']; lon_val = row.iloc[0]['lon']
    
    uid = session.get('user_id', 'admin') if session else 'admin'
    
    # DB 조회
    settings = {}
    try:
        settings = load_user_settings(uid) 
    except Exception as e:
        print(f"Panel DB Load Error: {e}")

    target_data = settings.get(locked, {})
    
    risk = target_data.get('risk_level', 'G')
    aircraft_txt = target_data.get('main_aircraft')
    if not aircraft_txt: aircraft_txt = "정보 없음"
    
    notes_txt = target_data.get('special_notes')
    if not notes_txt: notes_txt = "특이사항 없음"

    # [수정] 테마에 따른 텍스트 색상 결정
    # theme가 'dark'이면 흰색 글씨, 아니면(light) 검은색 글씨
    is_dark = (theme == 'dark' if theme else True)
    notes_text_cls = "small opacity-75 text-white" if is_dark else "small opacity-75 text-dark"

    risk_color = {'G':'success', 'A':'warning', 'R':'danger'}.get(risk, 'success')
    box_bg = "rgba(255,255,255,0.05)" if is_dark else "rgba(0,0,0,0.05)"
    t_str = f"{t_val:02d}:00" if t_val is not None else "12:00"
    link = f"/analysis?base={locked}&date={d_val}&time={t_str}"
    
    is_secure = local_settings.get('secure_mode', False) if local_settings else False
    if is_secure: coord_ui = html.Span("LAT: **.**** LON: ***.****", style={'fontFamily': 'monospace'})
    else: coord_ui = html.Span(f"LAT: {lat_val:.4f} LON: {lon_val:.4f}", style={'fontFamily': 'monospace'})

    return html.Div([
        html.Div([
            html.H2(k_name, className="text-neon fw-bold mb-0 me-2"), 
            dbc.Badge(risk, color=risk_color, className="rounded-circle d-flex align-items-center justify-content-center shadow-sm", style={'width':'32px', 'height':'32px', 'fontSize':'1.1rem', 'padding':'0'})
        ], className="d-flex align-items-center mb-1"),
        
        html.Div([html.Span(f"CODE: {locked}", className="me-3"), coord_ui], className="text-muted small mb-3"),
        
        html.Div([
            html.Div("PRIMARY THREAT", className="small fw-bold text-muted"), 
            html.Div(aircraft_txt, className="text-danger fw-bold fs-5")
        ], className="mb-2 p-2 border border-danger rounded", style={'backgroundColor': box_bg}), 
        
        # [수정] notes_text_cls 적용
        html.Div([
            html.Div([html.I(className="fas fa-sticky-note me-2"), "TACTICAL NOTES"], className="small fw-bold text-muted mb-1"), 
            html.Div(notes_txt, className=notes_text_cls, style={'whiteSpace': 'pre-wrap', 'fontSize':'0.85rem'})
        ], className="mb-3 p-2 border border-secondary rounded bg-opacity-10 bg-black", style={'minHeight': '50px'}),
        
        dcc.Link(dbc.Button([html.I(className="fas fa-satellite-dish me-2"), "정밀 영상 분석"], color="danger", className="w-100 fw-bold pulse-button", size="lg"), href=link)
    ])

@callback(Output('bookmark-store', 'data'), Input({'type': 'bookmark-btn', 'index': ALL}, 'n_clicks'), State('bookmark-store', 'data'), prevent_initial_call=True)
def toggle_bookmark(n_clicks, bookmarks):
    trigger = ctx.triggered_id
    if not trigger or not any(n_clicks): return no_update
    target_base = trigger['index']
    if bookmarks is None: bookmarks = []
    if target_base in bookmarks: bookmarks.remove(target_base)
    else: bookmarks.append(target_base)
    return bookmarks

@callback(Output("ops-map", "figure"), Output("base-list", "children"), Output("alert-log-box", "children"), Output("slider-status-text", "children"), Input("time-slider", "value"), Input("scenario-store", "data"), Input("history-store", "data"), Input("status-tabs", "active_tab"), Input("locked-target-store", "data"), Input("bookmark-store", "data"), Input("history-period-selector", "value"), Input("local-settings", "data"), State("user-session-store", "data"))
def update_view(slider, scen_data, hist_data, tab, locked, bookmarks, period, local_settings, session):
    trig_id = ctx.triggered_id
    if slider is None: slider = datetime.now().hour - (datetime.now().hour % 2)
    time_key = f"{slider:02d}:00"
    
    uid = session.get('user_id', 'admin') if session else 'admin'
    
    try:
        settings = load_user_settings(uid)
    except Exception:
        settings = {}

    is_secure = local_settings.get('secure_mode', False) if local_settings else False
    scen_df = process_scenario_data(scen_data)
    
    markers = []; items = []
    map_center = dict(lat=39.5, lon=127.5); map_zoom = 6.5
    
    if not scen_df.empty:
        cur_df = scen_df[scen_df['hour'] == slider]
        prev_h = slider - 2 if slider >= 2 else 22
        prev_df = scen_df[scen_df['hour'] == prev_h]
        
        cur_cnt = cur_df.set_index('base_name')['total_count'].to_dict()
        prev_cnt = prev_df.set_index('base_name')['total_count'].to_dict()
        
        bases = scen_df[['base_name', 'name_kor', 'lat', 'lon']].drop_duplicates(subset=['base_name']).dropna(subset=['name_kor']).sort_values(by='name_kor')
        
        for _, r in bases.iterrows():
            b = r['base_name']; k_name = r['name_kor']; lat_val = r['lat']; lon_val = r['lon']
            cur = int(cur_cnt.get(b, 0)); prev = int(prev_cnt.get(b, 0)); diff = cur - prev
            is_alert = (diff != 0)
            
            color = '#FF1744' if is_alert else "#535C58"
            p_size = PIN_SIZE_ALERT if is_alert else PIN_SIZE_NORMAL
            markers.append({'lat': lat_val, 'lon': lon_val, 'text': k_name, 'color': color, 'size': p_size, 'name': b})
            
            if (tab=='tab-alert' and not is_alert) or (tab=='tab-fav' and b not in (bookmarks or [])): continue
            
            risk = settings.get(b, {}).get('risk_level', 'G')
            
            risk_color = {'G':'success', 'A':'warning', 'R':'danger'}.get(risk, 'success')
            status_text = "ALERT" if is_alert else "STABLE"
            status_badge_color = "danger" if is_alert else "secondary"
            
            if diff > 0: diff_ui = html.Span(f"▲ {diff}", className="text-danger fw-bold ms-2 small")
            elif diff < 0: diff_ui = html.Span(f"▼ {abs(diff)}", className="text-primary fw-bold ms-2 small")
            else: diff_ui = html.Span("-", className="text-muted ms-2 small")
            
            is_locked = (b == locked)
            bg_style = {'backgroundColor': 'rgba(0,123,255,0.2)' if is_locked else 'rgba(255,255,255,0.05)', 'border': '1px solid #00d2d3' if is_locked else 'none', 'transition': '0.2s'}
            
            if is_secure: coord_text = "LAT: **.**** LON: ***.****"
            else: coord_text = f"LAT: {lat_val:.4f}  LON: {lon_val:.4f}"
            
            items.append(dbc.ListGroupItem([
                html.Div([
                    html.I(className=f"fas fa-star {'text-warning' if b in (bookmarks or []) else 'text-muted'} me-3", id={'type': 'bookmark-btn', 'index': b}, style={'cursor':'pointer'}),
                    html.Div([
                        html.Div([html.Span(k_name, className="fw-bold fs-5 me-2"), dbc.Badge(risk, color=risk_color, className="rounded-circle small", style={'width':'20px', 'height':'20px', 'lineHeight':'15px', 'padding':'0'})], className="d-flex align-items-center mb-1"),
                        html.Div([html.Span(f"({b})", className="text-muted small me-2"), dbc.Badge(status_text, color=status_badge_color, className="small me-2"), html.Span(f"식별: {cur}기", className="small opacity-75"), diff_ui], className="d-flex align-items-center mb-1"),
                        html.Div(coord_text, className="text-muted small", style={'fontSize': '0.7rem', 'fontFamily': 'monospace'})
                    ], id={'type': 'target-click-area', 'index': b}, style={'cursor':'pointer', 'flex':1})
                ], className="d-flex align-items-center")
            ], className="mb-1 shadow-sm", style=bg_style))
    
    if not items: items = html.Div("데이터 없음", className="text-center text-muted mt-5")

    log_items = []
    combined_df = pd.DataFrame()
    try:
        if not scen_df.empty:
            s_part = scen_df[['timestamp', 'base_name', 'name_kor', 'total_count', 'dt']].copy()
            combined_df = pd.concat([combined_df, s_part])
        if hist_data:
            h_df = pd.DataFrame(hist_data)
            if not h_df.empty and 'timestamp' in h_df.columns:
                h_df['dt'] = pd.to_datetime(h_df['timestamp'])
                h_part = h_df[['timestamp', 'base_name', 'name_kor', 'total_count', 'dt']].copy()
                combined_df = pd.concat([combined_df, h_part])
        if not combined_df.empty:
            combined_df = combined_df.drop_duplicates(subset=['base_name', 'dt']).sort_values(by=['base_name', 'dt'])
            combined_df['prev_count'] = combined_df.groupby('base_name')['total_count'].shift(1)
            combined_df['diff'] = combined_df['total_count'] - combined_df['prev_count']
            hours_int = int(period) if period else 24
            if hours_int == 24: limit_dt = datetime.strptime(f"{SIMULATION_TODAY} 00:00:00", "%Y-%m-%d %H:%M:%S")
            else: limit_dt = datetime.strptime(f"{SIMULATION_TODAY} 23:59:59", "%Y-%m-%d %H:%M:%S") - timedelta(hours=hours_int)
            display_df = combined_df[combined_df['dt'] >= limit_dt].sort_values(by='dt', ascending=False)
            records = display_df.to_dict('records')
            for r in records:
                diff_val = r['diff']
                if pd.isna(diff_val) or diff_val == 0: continue
                diff_val = int(diff_val)
                t_str = r['dt'].strftime("%m-%d %H:%M")
                if diff_val > 0: msg_ui = html.Span(f"▲ {diff_val}기 (증가)", className="text-danger fw-bold small")
                else: msg_ui = html.Span(f"▼ {abs(diff_val)}기 (감소)", className="text-primary fw-bold small")
                log_items.append(html.Div([html.Div([html.Span(t_str, className="small text-muted me-2"), html.Span(f"{r['name_kor']} ({r['base_name']})", className="fw-bold me-2 small"), dbc.Badge("ALERT", color="danger", className="small", style={'fontSize':'0.6rem'})], className="d-flex align-items-center mb-1"), html.Div(msg_ui, className="ms-1")], className="border-bottom border-secondary py-2"))
    except: pass
    if not log_items: log_items = html.Div("최근 이상징후 기록 없음", className="text-center text-muted mt-4 small")

    fig = go.Figure()
    if locked and markers:
        sel = next((m for m in markers if m['name'] == locked), None)
        if sel: fig.add_trace(go.Scattermapbox(lat=[sel['lat']], lon=[sel['lon']], mode='markers', marker=dict(size=PIN_SIZE_SELECTED_OUTER, color='#FFD700', opacity=0.5), hoverinfo='skip'))
    if markers:
        fig.add_trace(go.Scattermapbox(lat=[m['lat'] for m in markers], lon=[m['lon'] for m in markers], mode='markers', marker=dict(size=[m['size'] for m in markers], color=[m['color'] for m in markers], opacity=0.9), text=[m['text'] for m in markers], customdata=[m['name'] for m in markers], hoverinfo='text'))
    if locked and markers:
        sel = next((m for m in markers if m['name'] == locked), None)
        if sel:
             fig.add_trace(go.Scattermapbox(lat=[sel['lat']], lon=[sel['lon']], mode='markers', marker=dict(size=PIN_SIZE_SELECTED_MID+2, color='white', opacity=1.0), hoverinfo='skip'))
             fig.add_trace(go.Scattermapbox(lat=[sel['lat']], lon=[sel['lon']], mode='markers', marker=dict(size=PIN_SIZE_SELECTED_MID, color=sel['color'], opacity=1.0), hoverinfo='skip'))
    fig.update_layout(mapbox_style="open-street-map", mapbox=dict(center=map_center, zoom=map_zoom), margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False, uirevision='constant_view')
    final_items = items
    if trig_id == "scenario-store" and locked: final_items = no_update
    
    return fig, final_items, log_items, f"VIEW: {time_key}"