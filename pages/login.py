import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from db_manager import run_query, log_action

dash.register_page(__name__, path='/')

def layout():
    return html.Div([
        html.Div(className="login-wrapper", children=[
            
            html.Div(className="glass-panel login-card shadow-lg", children=[
                html.Div("AUTO-SORTIE", className="login-logo"),
                html.Div("ROKAF STRATEGIC SURVEILLANCE", className="text-muted small mb-1 fw-bold", style={'color': '#bdc3c7 !important'}), 
                html.Div("CLASSIFIED - LEVEL 2 ACCESS", className="security-badge"),
                
                html.Div([
                    dbc.Input(id="login-id", placeholder="SERVICE NUMBER (군번)", type="text", className="login-input"),
                    dbc.Input(id="login-pw", placeholder="SECURITY CODE (비밀번호)", type="password", className="login-input"),
                    
                    # [보안 서약 체크박스]
                    html.Div([
                        dbc.Checkbox(
                            id="security-check",
                            value=False,
                            className="custom-checkbox" 
                        ),
                        html.Label(
                            "본 시스템은 2급 군사기밀을 포함하고 있으며, 무단 유출 시 군사기밀보호법에 의거 처벌받음을 인지하고 이에 동의합니다.",
                            htmlFor="security-check",
                            className="security-check-label ms-2",
                            style={'cursor': 'pointer'}
                        ),
                    ], className="d-flex align-items-center mt-3 mb-2 px-1"),

                    html.Div(id="login-alert", className="text-danger small fw-bold mt-2", style={'minHeight': '20px'}),
                    
                    dbc.Button("AUTHENTICATE (접속 인증)", id="login-btn", className="btn-login"),
                ], className="mt-4"),
                
                html.Div([
                    html.P("ACCESS RESTRICTED TO AUTHORIZED PERSONNEL ONLY", className="text-muted mt-4 mb-0", style={'fontSize': '0.7rem', 'color': '#888 !important'}),
                    html.P("© 2025 ROKAF STRATEGIC COMMAND", className="text-muted", style={'fontSize': '0.6rem', 'color': '#888 !important'})
                ])
            ])
        ]),
        
        dcc.Location(id='login-redirect', refresh=True),
    ], id='login-container')

@callback(
    Output('login-redirect', 'pathname'),
    Output('login-alert', 'children'),
    Output('user-session-store', 'data', allow_duplicate=True),
    Input('login-btn', 'n_clicks'),
    State('login-id', 'value'),
    State('login-pw', 'value'),
    State('security-check', 'value'),
    prevent_initial_call=True
)
def handle_login(n_clicks, user_id, user_pw, security_agreed):
    if not user_id or not user_pw:
        return no_update, "⚠️ 군번과 비밀번호를 입력하십시오.", no_update

    if not security_agreed:
        return no_update, "⚠️ 보안 서약에 동의해야 접속할 수 있습니다.", no_update

    try:
        # [DB 연결] tb_users 테이블 조회
        query = "SELECT * FROM tb_users WHERE user_id = :uid"
        df = run_query(query, params={'uid': user_id})

        if not df.empty:
            # DB 데이터 매핑
            row = df.iloc[0]
            correct_pw = str(row['password'])
            
            if str(user_pw) == correct_pw:
                session_info = {
                    'user_id': row['user_id'],
                    'name': row['name'],
                    'rank': row['rank'],
                    'unit': row['unit'],
                    'clearance': row['clearance'],
                    'img': row['img_path']
                }
                
                # [수정 완료] 인자 순서 변경: (ID, Action)
                log_action(user_id, "LOGIN_SUCCESS")
                return "/home", None, session_info
            else:
                # [수정 완료] 인자 순서 변경
                log_action(user_id, "LOGIN_FAIL_PW")
                return no_update, "❌ 비밀번호가 일치하지 않습니다.", no_update
        else:
            print(f"Login Failed: Unknown ID {user_id}")
            return no_update, "❌ 등록되지 않은 군번입니다.", no_update
            
    except Exception as e:
        print(f"Login Error: {e}")
        return no_update, "⛔ 시스템 오류 발생", no_update