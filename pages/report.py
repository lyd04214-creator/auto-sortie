import dash
from dash import html, dcc, Input, Output, State, callback, no_update, callback_context
import dash_bootstrap_components as dbc
import base64
from datetime import datetime, timedelta
from db_manager import run_query
from utils.report_service import fetch_report_data, generate_multi_charts, create_pdf_bytes

dash.register_page(__name__, path='/report')

layout = dbc.Container([
    dcc.Download(id="download-pdf"),
    dbc.Row([
        dbc.Col([
            html.Div(className="glass-panel p-4 mt-3", children=[
                html.H4([html.I(className="fas fa-file-alt me-2"), "작전 리포트 센터"], className="text-neon fw-bold mb-4 border-bottom pb-3"),
                
                html.Label("1. 보고서 유형", className="fw-bold text-muted mb-1"),
                dcc.Dropdown(
                    id="rpt-type", 
                    options=[
                        {'label':'🚨 긴급 작전 (Emergency)','value':'emergency'},
                        {'label':'📅 일간 상황 (Daily)','value':'daily'},
                        {'label':'📈 주간 분석 (Weekly)','value':'weekly'},
                        {'label':'📉 월간 분석 (Monthly)','value':'monthly'},
                        {'label':'📆 연간 분석 (Yearly)','value':'yearly'}
                    ], value='emergency', clearable=False, className="mb-3"  # [수정] text-dark 삭제
                ),

                html.Label("2. 상세 수준", className="fw-bold text-muted mb-2"),
                dbc.RadioItems(id="rpt-detail", options=[{"label": "📑 요약", "value": "brief"}, {"label": "📊 상세", "value": "detailed"}], value="brief", inline=True, className="mb-3"),
                
                html.Div([
                    html.Label("3. 기간 및 대상 설정", className="fw-bold text-muted mb-0"),
                    html.I(className="fas fa-question-circle text-info ms-2", id="time-help-icon", style={'cursor':'pointer', 'fontSize': '1.1rem'})
                ], className="d-flex align-items-center mb-2"),
                
                dbc.Tooltip("주간/월간/연간 선택 시, 해당 기간 내 '아무 날짜'나 선택하면 자동으로 전체 기간이 설정됩니다.", target="time-help-icon", placement="right"),
                
                dbc.Row([
                    dbc.Col(dcc.DatePickerRange(id='rpt-date', className="mb-2 w-100", display_format='YYYY-MM-DD'), width=8),
                    dbc.Col(html.Div(id='time-dropdown-container', children=[
                        dcc.Dropdown(id='rpt-time', options=[{'label': f"{i:02d}:00", 'value': f"{i:02d}:00"} for i in range(0, 24, 2)], value="12:00", clearable=False, placeholder="시간")
                    ]), width=4)
                ], className="g-1 mb-2"),
                
                # [수정] text-dark 삭제
                dcc.Dropdown(id="rpt-base", options=[], placeholder="대상 기지 선택", className="mb-4"),

                html.Hr(className="border-secondary"),
                
                # [수정] text-white -> text-info (파란색으로 변경하여 양쪽 테마 모두 보이게 함)
                html.Label("4. 메타데이터", className="fw-bold text-secondary mb-2"),
                dbc.Row([
                    # [수정] text-dark 삭제
                    dbc.Col([dbc.Label("수신", className="text-muted small"), dbc.Input(id="rpt-to", placeholder="예: 작전사령관", size="sm", className="mb-2")], width=6),
                    dbc.Col([dbc.Label("참조", className="text-muted small"), dbc.Input(id="rpt-cc", placeholder="예: 정보처장", size="sm", className="mb-2")], width=6),
                ]),
                # [수정] text-dark 삭제
                dbc.Textarea(id="rpt-comment", placeholder="분석관 의견 입력...", style={'height': '80px'}, className="mb-4 mt-2"),
                
                dbc.Button([html.I(className="fas fa-file-pdf me-2"), "PDF 생성"], id="btn-download", color="danger", className="w-100 fw-bold shadow-sm py-2")
            ])
        ], width=4),
        
        dbc.Col([
            # [수정] backgroundColor 하드코딩 삭제 -> glass-panel 클래스가 알아서 처리하게 둠
            # 만약 우측을 항상 어둡게 하고 싶다면 style에 'backgroundColor': 'rgba(0,0,0,0.5)' 권장
            html.Div(className="glass-panel p-0 mt-3 h-100 d-flex justify-content-center align-items-start", style={'overflowY': 'auto'}, children=[
                html.Div(
                    id="preview-area", 
                    className="shadow-lg", 
                    style={
                        'width': '210mm', 
                        'minHeight': '297mm', 
                        'backgroundColor': 'white', # 종이는 항상 흰색
                        'padding': '20mm', 
                        'color': 'black',           # 글자는 항상 검은색
                        'marginTop': '20px', 
                        'marginBottom': '20px'
                    },
                    **{'data-bs-theme': 'light'}
                )
            ])
        ], width=8)
    ])
], fluid=True, className="pb-5")

@callback(Output('time-dropdown-container', 'style'), Input('rpt-type', 'value'))
def toggle_time_dropdown(rtype):
    return {'display': 'block'} if rtype == 'emergency' else {'display': 'none'}

@callback(Output('rpt-base', 'options'), Input('rpt-type', 'value'))
def load_bases_ui(v):
    sql = "SELECT scene_name, name_kor FROM tb_scene WHERE name_kor IS NOT NULL AND name_kor != '' ORDER BY name_kor ASC"
    df = run_query(sql)
    return [{'label': '전 기지 (ALL)', 'value': 'ALL'}] + [{'label': f"{r['name_kor']} ({r['scene_name']})", 'value': r['scene_name']} for _, r in df.iterrows()]

@callback(
    [Output('rpt-date', 'start_date'), Output('rpt-date', 'end_date')],
    [Input('rpt-type', 'value'), Input('rpt-date', 'start_date')]
)
def smart_date_setter(rtype, user_picked_start):
    ctx = callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else 'rpt-type'
    
    today = datetime.now()
    ref_date = today

    if trigger_id == 'rpt-date' and user_picked_start:
        try: ref_date = datetime.strptime(user_picked_start, "%Y-%m-%d")
        except: pass

    start_date, end_date = ref_date, ref_date

    if rtype == 'weekly':
        start_date = ref_date - timedelta(days=ref_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif rtype == 'monthly':
        start_date = ref_date.replace(day=1)
        if start_date.month == 12: next_month = start_date.replace(year=start_date.year+1, month=1, day=1)
        else: next_month = start_date.replace(month=start_date.month+1, day=1)
        end_date = next_month - timedelta(days=1)
    elif rtype == 'yearly':
        start_date = ref_date.replace(month=1, day=1)
        end_date = ref_date.replace(month=12, day=31)
    else:
        if trigger_id == 'rpt-date': return no_update
        start_date = today; end_date = today

    if end_date > today: end_date = today
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

@callback(
    Output('preview-area', 'children'), 
    [Input('rpt-type', 'value'), Input('rpt-base', 'value'), 
     Input('rpt-date', 'start_date'), Input('rpt-date', 'end_date'), Input('rpt-time', 'value'),
     Input('rpt-detail', 'value'), Input('rpt-to', 'value'), Input('rpt-cc', 'value'), Input('rpt-comment', 'value')]
)
def update_preview_ui(rtype, base, start, end, target_time, detail_level, r_to, r_cc, comment):
    if not base or not start: 
        return html.Div("설정 대기 중...", className="text-center text-muted mt-5 pt-5", style={'color': 'black'})
    
    df, is_comparison_mode = fetch_report_data(rtype, base, start, end, target_time)
    
    chart_divs = []
    if not df.empty:
        chart_imgs = generate_multi_charts(df, rtype, is_comparison_mode)
        for buf in chart_imgs:
            b64 = base64.b64encode(buf.getvalue()).decode()
            chart_divs.append(html.Img(src=f"data:image/png;base64,{b64}", style={'width':'100%', 'border': '1px solid #eee', 'marginBottom': '10px'}))

    if not df.empty:
        if rtype == 'emergency':
            col_labels = {'dt_str':'시간', 'name_kor':'기지명', 'total_count':'식별', 'status_str':'상태', 'diff_str':'변동', 'risk_degree':'위험도', 'main_aircraft':'주력기', 'remarks':'특이사항'}
            target_cols = ['dt_str', 'name_kor', 'total_count', 'status_str', 'diff_str', 'risk_degree', 'main_aircraft', 'remarks']
            df_table = df.sort_values('timestamp').groupby('name_kor', as_index=False).tail(1)
        elif rtype == 'daily':
            col_labels = {'dt_str':'시간', 'name_kor':'기지명', 'total_count':'식별수', 'risk_degree':'위험도', 'main_aircraft':'주력기', 'remarks':'특이사항'}
            target_cols = ['dt_str', 'name_kor', 'total_count', 'risk_degree', 'main_aircraft', 'remarks']
            df_table = df
        else:
            col_labels = {'dt_str':'일자', 'name_kor':'기지명', 'min_count':'최소', 'avg_count':'평균', 'max_count':'최대', 'risk_degree':'위험도', 'main_aircraft':'주력기', 'remarks':'특이사항'}
            target_cols = ['dt_str', 'name_kor', 'min_count', 'avg_count', 'max_count', 'risk_degree', 'main_aircraft', 'remarks']
            df_table = df
        
        valid_cols = [c for c in target_cols if c in df_table.columns]
        rows = 20
        df_show = df_table[valid_cols].head(rows).rename(columns=col_labels)
        
        # [핵심 수정] 표 스타일 강제 주입 (CSS 변수 오버라이딩)
        data_table = html.Div([
            dbc.Table.from_dataframe(
                df_show, 
                striped=True, 
                bordered=True, 
                hover=True, 
                size='sm', 
                style={
                    'textAlign': 'center', 
                    'whiteSpace': 'normal', 
                    'wordBreak': 'break-all',
                    'color': 'black',              # 글자색 강제 검정
                    'borderColor': '#000000',      # 테두리 강제 검정
                    '--bs-table-color': 'black',   # 부트스트랩 변수 덮어쓰기 (중요!)
                    '--bs-table-bg': 'transparent',
                    '--bs-table-striped-color': 'black',
                    '--bs-table-active-color': 'black',
                    '--bs-table-hover-color': 'black'
                }
            )
        ])
        
    else:
        data_table = html.Div("데이터 없음", className="text-center p-5", style={'color': 'black'})

    title_map = {'emergency': '긴급 작전', 'daily': '일간 상황', 'weekly': '주간 분석', 'monthly': '월간 분석', 'yearly': '연간 분석'}
    
    # [수정] 전체 컨테이너에도 color: black을 style로 직접 주입
    return html.Div([
        html.Div([
            html.Div("Ⅱ급 비밀 (SECRET)", className="fw-bold fs-5", style={'letterSpacing': '2px', 'color': '#dc3545'}),
            html.H2(f"{title_map.get(rtype, '작전')} 보고서", className="fw-bold mt-2", style={'borderBottom': '2px solid black', 'paddingBottom': '10px', 'color': 'black'})
        ], className="mb-4 text-center"),
        
        html.Div([
            dbc.Row([dbc.Col(f"수신: {r_to or '-'}", width=6), dbc.Col(f"일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}", width=6)]),
            dbc.Row([dbc.Col(f"참조: {r_cc or '-'}", width=6), dbc.Col(f"기간: {start} ~ {end}", width=6)])
        ], className="mb-4 p-3 border rounded", style={'backgroundColor': '#f8f9fa', 'color': 'black', 'borderColor': '#dee2e6'}),
        
        html.Div([
            html.H5("1. 종합 의견", className="fw-bold border-bottom pb-1", style={'color': 'black', 'borderColor': 'black'}), 
            html.P(comment or "특이사항 없음.", style={'whiteSpace': 'pre-wrap', 'color': 'black'})
        ], className="mb-4"),
        
        html.Div([
            html.H5("2. 시각화 분석", className="fw-bold border-bottom pb-1", style={'color': 'black', 'borderColor': 'black'}), 
            html.Div(chart_divs) if chart_divs else html.Div("데이터 부족", className="text-center p-3", style={'color': 'black'})
        ]),
        
        html.Div([
            html.H5(f"3. 상세 로그 ({'요약' if detail_level=='brief' else '전체'})", className="fw-bold border-bottom pb-1", style={'color': 'black', 'borderColor': 'black'}), 
            data_table
        ])
    ], style={'color': 'black'}) # 최상위 Div에서 검은색 강제

@callback(Output('download-pdf', 'data'), Input('btn-download', 'n_clicks'),
    State('rpt-type', 'value'), State('rpt-base', 'value'), State('rpt-date', 'start_date'), State('rpt-date', 'end_date'), State('rpt-time', 'value'),
    State('rpt-to', 'value'), State('rpt-cc', 'value'), State('rpt-comment', 'value'), prevent_initial_call=True)
def generate_pdf_ui(n, rtype, base, start, end, target_time, r_to, r_cc, comment):
    pdf_bytes = create_pdf_bytes(rtype, base, start, end, target_time, r_to, r_cc, comment)
    if pdf_bytes: return dcc.send_bytes(pdf_bytes, f"Report_{rtype}_{base}_{start}.pdf")
    return no_update