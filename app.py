import dash
from dash import html, dcc, Input, Output, State, clientside_callback, no_update, callback
import dash_bootstrap_components as dbc
from db_manager import log_action
import time

# [설정] 로고 경로
LOGO_LIGHT_PATH = "/assets/images/logo_light.png"
LOGO_DARK_PATH = "/assets/images/logo_dark.png"

# [핵심] 서버 사이드 클릭 기록 저장소 (User ID별 타임스탬프 관리)
# 예: {'20-1234': [1704421200.1, 1704421200.5, ...]}
SERVER_CLICK_HISTORY = {}

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP, 
        "https://fonts.googleapis.com/css2?family=Black+Ops+One&family=Rajdhani:wght@500;700&family=Noto+Sans+KR:wght@400;700&display=swap",
        "https://use.fontawesome.com/releases/v6.4.2/css/all.css"
    ],
    suppress_callback_exceptions=True,
    title="ROKAF Auto Sortie"
)
server = app.server

# --- [Top Navbar] ---
navbar = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                dbc.Row(
                    [
                        dbc.Col(html.Img(id="navbar-logo", src=LOGO_DARK_PATH, height="60px"), className="me-2"),
                    ],
                    align="center",
                    className="g-0",
                ),
                href="/home",
                style={"textDecoration": "none"},
            ),
            dbc.Nav(
                [
                    dbc.NavItem(dbc.NavLink("작전 지도", href="/home", active="exact", className="nav-link-custom")),
                    dbc.NavItem(dbc.NavLink("영상 분석", href="/analysis", active="exact", className="nav-link-custom")),
                    dbc.NavItem(dbc.NavLink("리포트 생성", href="/report", active="exact", className="nav-link-custom")),
                    html.Div(className="vr mx-3 my-auto", style={'height': '24px', 'backgroundColor': 'var(--border-color)'}),
                    html.Div([
                        html.I(className="fas fa-sun me-2", style={'color': 'var(--text-secondary)'}),
                        dbc.Switch(id="theme-switch", value=True, className="d-inline-block", persistence=True),
                        html.I(className="fas fa-moon ms-2", style={'color': 'var(--text-secondary)'}),
                    ], className="d-flex align-items-center me-3"),
                    dbc.DropdownMenu(
                        id="user-nav-dropdown",
                        children=[
                            dbc.DropdownMenuItem("내 정보", href="/mypage"),
                            dbc.DropdownMenuItem("환경 설정", href="/settings"),
                            dbc.DropdownMenuItem(divider=True),
                            dbc.DropdownMenuItem("로그아웃", href="/", className="text-danger"),
                        ],
                        nav=True,
                        in_navbar=True,
                        label=html.Span([html.I(className="fas fa-user-secret me-2"), "COMMANDER"], id="user-nav-label"),
                        align_end=True,
                        className="nav-link-custom p-0"
                    ),
                ],
                className="ms-auto align-items-center",
                navbar=True,
            ),
        ],
        fluid=True,
    ),
    color="transparent", 
    className="navbar-custom fixed-top"
)

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='theme-store', storage_type='local'), 
    dcc.Store(id='user-session-store', storage_type='session'),
    html.Div(id='navbar-container', children=navbar),
    html.Div(dash.page_container, id="page-content-container", style={"padding": "0", "minHeight": "100vh"})
], fluid=True, id="main-container", className="p-0 m-0", style={'minHeight': '100vh'})

@callback([Output('navbar-container', 'style'), Output('page-content-container', 'style')], Input('url', 'pathname'))
def toggle_navbar_layout(pathname):
    if pathname == '/' or pathname is None:
        return {'display': 'none'}, {"padding": "0", "minHeight": "100vh"}
    else:
        return {'display': 'block'}, {"paddingTop": "85px", "paddingLeft": "20px", "paddingRight": "20px", "minHeight": "100vh"}

clientside_callback(
    """function(value) {
        const theme = value ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
        return theme;
    }""",
    Output('theme-store', 'data'),
    Input('theme-switch', 'value')
)

@callback(Output('navbar-logo', 'src'), Input('theme-switch', 'value'))
def update_logo_src(is_dark):
    return LOGO_DARK_PATH if is_dark else LOGO_LIGHT_PATH

@callback(Output('user-nav-label', 'children'), Input('user-session-store', 'data'))
def update_nav_user_info(session_data):
    if session_data:
        return html.Span([html.I(className="fas fa-user-circle me-2"), f"{session_data.get('rank', '')} {session_data.get('name', 'User')}"])
    return html.Span([html.I(className="fas fa-user-secret me-2"), "COMMANDER"])

# [핵심 수정] 서버 사이드 매크로 탐지 로직
@callback(
    Output('user-session-store', 'data', allow_duplicate=True), 
    Input('url', 'pathname'), 
    State('user-session-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def track_page_view(pathname, session_data):
    # 세션 데이터가 없으면(로그아웃 등) 아무것도 안 함
    if not session_data:
        return no_update

    user_id = session_data.get('user_id', 'GUEST')

    # 루트('/')가 아니고 유효한 페이지일 때만 로직 수행
    if pathname and pathname != '/':
        
        # 1. 전역 변수에서 해당 유저의 기록 가져오기
        global SERVER_CLICK_HISTORY
        if user_id not in SERVER_CLICK_HISTORY:
            SERVER_CLICK_HISTORY[user_id] = []
        
        # 2. 현재 시간 측정 및 기록 업데이트
        now = time.time()
        # 1.0초 이내의 기록만 남기고 필터링 (오래된 기록 삭제)
        SERVER_CLICK_HISTORY[user_id] = [t for t in SERVER_CLICK_HISTORY[user_id] if now - t < 1.0]
        SERVER_CLICK_HISTORY[user_id].append(now) # 현재 클릭 추가
        
        current_cps = len(SERVER_CLICK_HISTORY[user_id]) # 현재 초당 클릭 수 (Clicks Per Second)

        # 3. [보안] 매크로 탐지 (1초 내 3회 이상)
        if current_cps >= 3:
            print(f"🚨 [SECURITY] MACRO DETECTED! User: {user_id}, Rate: {current_cps} clicks/sec")
            # 경고 로그 적재
            log_action(user_id, "MACRO_DETECTED", details=f"Rate: {current_cps}/sec @ {pathname}")
        
        # 4. 정상 페이지 뷰 기록
        log_action(user_id, "PAGE_VIEW", details=pathname)

    # 세션은 변경사항이 없으므로 업데이트하지 않음 (서버 변수로 처리했기 때문)
    return no_update

if __name__ == "__main__":
    app.run(debug=True, port=8050)