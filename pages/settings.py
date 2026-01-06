import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from db_manager import run_query, execute_query

dash.register_page(__name__, path='/settings')

# -----------------------------------------------------------------------------
# [레이아웃 구성]
# -----------------------------------------------------------------------------
layout = dbc.Container([
    # 세션 및 로컬 저장소
    dcc.Store(id='st-sess', storage_type='session'),
    
    # [중요] 시스템 설정 공유용 저장소 (쓰기 전용으로 활용)
    dcc.Store(id='local-settings', storage_type='local'),

    # [수정] 상단 여백 축소 
    html.Div(className="glass-panel p-3 mt-0", style={'maxWidth': '1000px', 'margin': '0 auto'}, children=[
        
        # 헤더
        html.Div([
            html.H2([html.I(className="fas fa-sliders-h me-2"), "환경 설정"], className="text-primary fw-bold mb-0"),
            html.Small("작전 환경 및 기지별 전술 정보를 설정합니다.", className="text-muted")
        ], className="border-bottom border-secondary pb-3 mb-4"),

        # 탭 구조
        dbc.Tabs([
            # -----------------------------------------------------------------
            # [TAB 1] 기지별 전술 설정 (DB 저장 -> 메인 리스트 엠블럼 반영)
            # -----------------------------------------------------------------
            dbc.Tab(label="기지별 전술 설정", tab_id="tab-base", label_class_name="fw-bold", children=[
                dbc.Row([
                    # [좌측] 기지 선택
                    dbc.Col([
                        html.Label("대상 기지 선택", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='st-base', 
                            className="mb-4", 
                            placeholder="기지명을 검색하거나 선택하십시오...", 
                            clearable=False
                        ),
                        html.Div(id="st-current-info", className="p-3 border rounded bg-light text-muted small")
                    ], width=4, className="border-end border-secondary pe-4"),

                    # [우측] 상세 설정
                    dbc.Col([
                        html.H5("전술 데이터 입력", className="fw-bold mt-3 mb-3 border-bottom border-secondary pb-2"),
                        
                        # (1) 위협 등급 (메인페이지 엠블럼 색상 결정)
                        html.Label("위협 등급 (Risk Level - 엠블럼)", className="fw-bold mb-2"),
                        html.Div("※ 메인 리스트의 원형 뱃지(Emblem) 색상이 변경됩니다.", className="text-muted small mb-2"),
                        dbc.RadioItems(
                            id="st-risk",
                            options=[
                                {"label": "🟢 GREEN (정상)", "value": "G"},
                                {"label": "🟡 AMBER (주의)", "value": "A"},
                                {"label": "🔴 RED (위협)", "value": "R"},
                            ],
                            value="G",
                            inline=True,
                            className="mb-4",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-secondary", 
                            labelCheckedClassName="active"
                        ),

                        # (2) 주력기 & 특이사항
                        dbc.Row([
                            dbc.Col([
                                html.Label("배치 주력기 (Main Assets)", className="fw-bold mb-2"),
                                dbc.Input(id="st-aircraft", placeholder="예: MIG-29, SU-25", className="mb-3")
                            ], width=12),
                            dbc.Col([
                                html.Label("전술적 특이사항 (Tactical Notes)", className="fw-bold mb-2"),
                                dbc.Textarea(id="st-notes", placeholder="특이사항 입력...", className="mb-3", style={'height': '120px'})
                            ], width=12)
                        ]),

                        html.Hr(className="border-secondary"),
                        dbc.Row([
                            dbc.Col(html.Div(id="st-msg", className="fw-bold mt-2 small"), width=8),
                            dbc.Col(dbc.Button([html.I(className="fas fa-save me-2"), "설정 저장"], id="st-save", color="primary", className="w-100 fw-bold shadow-sm"), width=4)
                        ], className="align-items-center")

                    ], width=8, className="ps-4")
                ], className="pt-2")
            ]),

            # -----------------------------------------------------------------
            # [TAB 2] 시스템 표시 설정 (Local Storage)
            # -----------------------------------------------------------------
            dbc.Tab(label="시스템 표시 설정", tab_id="tab-system", label_class_name="fw-bold", children=[
                html.Div(className="p-4", children=[
                    html.H5("화면 표시 옵션", className="fw-bold mb-3"),
                    
                    # (1) 보안 모드 (persistence=True 적용으로 에러 해결)
                    dbc.Card(className="border mb-3 shadow-sm", children=[
                        dbc.CardBody([
                            html.Div([
                                html.H6([html.I(className="fas fa-user-secret me-2"), "보안 브리핑 모드 (Secure Mode)"], className="fw-bold text-warning"),
                                # [핵심 수정] persistence=True 추가 (스스로 상태 기억)
                                dbc.Switch(id="opt-secure-mode", value=False, className="fs-4", persistence=True, persistence_type='local')
                            ], className="d-flex justify-content-between align-items-center"),
                            html.Div("활성화 시 지도 및 리스트의 정확한 좌표(Lat/Lon) 정보를 마스킹(**.***) 처리하여 보안을 유지합니다.", className="text-muted small mt-1")
                        ])
                    ])
                ])
            ])

        ], className="custom-tabs", active_tab="tab-base")
    ])
], fluid=True, className="py-4")


# -----------------------------------------------------------------------------
# [Callbacks]
# -----------------------------------------------------------------------------

# 1. 기지 목록 로드 (데이터 정제: 한글명 없는 것 제외)
@callback(Output('st-base', 'options'), Input('st-sess', 'data'))
def load_base_options(sess):
    try:
        # [핵심] 한글명(name_kor)이 없는 데이터(숫자만 있거나 NULL)는 제외
        sql = """
            SELECT scene_name, name_kor 
            FROM tb_scene 
            WHERE name_kor IS NOT NULL 
              AND name_kor != '' 
            ORDER BY name_kor ASC
        """
        df = run_query(sql)
        
        if df.empty: return []
        
        # 한글명 (영문코드) 형식
        return [{'label': f"{r['name_kor']} ({r['scene_name']})", 'value': r['scene_name']} for _, r in df.iterrows()]
    except Exception as e:
        print(f"Load Option Error: {e}")
        return []

# 2. 기지 설정 불러오기 (DB -> UI)
@callback(
    Output('st-risk', 'value'), Output('st-aircraft', 'value'), Output('st-notes', 'value'), Output('st-current-info', 'children'),
    Input('st-base', 'value'), State('user-session-store', 'data')
)
def load_settings(base, sess):
    if not base: return "G", "", "", "기지를 선택하십시오."
    uid = sess.get('user_id', 'admin') if sess else 'admin'
    
    # 설정 조회
    sql = "SELECT risk_level, main_aircraft, special_notes FROM tb_user_settings WHERE user_id=:u AND base_name=:b"
    df = run_query(sql, {'u': uid, 'b': base})
    
    # 기지 이름 조회
    info = run_query(f"SELECT name_kor FROM tb_scene WHERE scene_name = '{base}'")
    k_name = info.iloc[0]['name_kor'] if not info.empty else base
    
    msg = html.Div([html.Strong(f"[{k_name}]", className="text-primary"), " 설정을 불러왔습니다."])

    if not df.empty:
        r = df.iloc[0]
        return r['risk_level'], (r['main_aircraft'] or ""), (r['special_notes'] or ""), msg
    else:
        return "G", "", "", msg

# 3. 기지 설정 저장하기 (UI -> DB)
@callback(
    Output('st-msg', 'children'),
    Input('st-save', 'n_clicks'),
    State('st-base', 'value'), State('st-risk', 'value'), State('st-aircraft', 'value'), State('st-notes', 'value'),
    State('user-session-store', 'data'),
    prevent_initial_call=True
)
def save_settings(n, base, risk, aircraft, notes, sess):
    if not base: return html.Span("❌ 기지 선택 필요", className="text-danger")
    uid = sess.get('user_id', 'admin') if sess else 'admin'
    
    try:
        sql = """
            INSERT INTO tb_user_settings (user_id, base_name, risk_level, main_aircraft, special_notes)
            VALUES (:u, :b, :r, :a, :n)
            ON DUPLICATE KEY UPDATE risk_level=:r, main_aircraft=:a, special_notes=:n
        """
        execute_query(sql, {'u':uid, 'b':base, 'r':risk, 'a':aircraft, 'n':notes})
        return html.Span("✅ 저장 완료 (메인 페이지 엠블럼에 반영됨)", className="text-success")
    except Exception as e:
        print(f"Save Error: {e}")
        return html.Span("❌ 저장 실패", className="text-danger")

# 4. 시스템 설정 저장 (UI -> Local Store)
# [핵심 수정] 스토어에서 읽어오는 콜백을 삭제하고, 스위치 변경 시 저장하는 단방향 콜백만 남김
@callback(
    Output('local-settings', 'data'),
    Input('opt-secure-mode', 'value'),
    State('local-settings', 'data')
)
def update_local_settings(secure, current_data):
    if current_data is None: current_data = {}
    current_data['secure_mode'] = secure
    return current_data