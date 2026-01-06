import os
import io
import base64
import cv2
import math
import numpy as np
import pandas as pd
import requests
import urllib3
import plotly.graph_objects as go
import traceback
from dash import html
from PIL import Image, ImageOps
from functools import lru_cache
from db_manager import run_query, BASE_DIR
from datetime import datetime, timedelta
from PIL import ImageEnhance
from ultralytics import YOLO

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# [1. AI 모델 로드]
MODELS_DIR = os.path.join(BASE_DIR, 'models')
DET_MODEL = None
CLS_MODEL = None

try:
    from ultralytics import YOLO
    
    det_path = os.path.join(MODELS_DIR, 'det_best.pt')
    cls_path = os.path.join(MODELS_DIR, 'cls_best.pt')
    
    if os.path.exists(det_path):
        try: DET_MODEL = YOLO(det_path)
        except: pass
    if os.path.exists(cls_path):
        try: CLS_MODEL = YOLO(cls_path)
        except: pass

except ImportError:
    pass

# --- [2. 이미지 로더] ---
@lru_cache(maxsize=32)
def load_image_from_path(path):
    if not path: return None
    clean_path = str(path).strip().strip("'").strip('"')
    print(f"[AWS DOWNLOAD] {clean_path}", flush=True)
    
    try:
        if clean_path.startswith('http'):
            response = requests.get(clean_path, stream=True, timeout=10, verify=False)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                return img
        else:
            full_path = clean_path if os.path.isabs(clean_path) else os.path.join(BASE_DIR, 'assets', 'images', clean_path)
            if os.path.exists(full_path):
                return Image.open(full_path)
    except Exception:
        pass
    return None

def get_db_image_path(base, date_str, time_str):
    try: target_hour = int(time_str.split(':')[0])
    except: target_hour = 12 
    
    # [이미지] 시나리오 데이터면 날짜 무시하고 해당 시간대 이미지 가져옴
    query = """
    SELECT img_path FROM tb_scenario s
    JOIN tb_scene sc ON s.scene_id = sc.scene_id
    WHERE sc.scene_name = :bn
      AND s.data_type = 'SCENARIO'
      AND HOUR(s.timestamp) = :hr
    LIMIT 1
    """
    df = run_query(query, params={'bn': base, 'hr': target_hour})
    if not df.empty and df.iloc[0]['img_path']:
        return str(df.iloc[0]['img_path']).strip().strip("'").strip('"')
    return None

# --- [3. AI Logic] ---
def get_center_dist(boxA, boxB):
    cxA, cyA = (boxA[0]+boxA[2])/2, (boxA[1]+boxA[3])/2
    cxB, cyB = (boxB[0]+boxB[2])/2, (boxB[1]+boxB[3])/2
    return math.sqrt((cxA-cxB)**2 + (cyA-cyB)**2)

def py_cpu_nms(dets, thresh=0.5):
    if len(dets) == 0: return []
    x1, y1, x2, y2 = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
    scores = dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]
    return keep

DEBUG_SAVE_DIR = "debug_crops"  # 이 폴더에 진단 이미지가 저장됩니다.
if not os.path.exists(DEBUG_SAVE_DIR):
    os.makedirs(DEBUG_SAVE_DIR)

@lru_cache(maxsize=32)
def cached_detection(path):
    # 1. 이미지 로드 (S3/Local 공통)
    im = load_image_from_path(path)
    if not im or not DET_MODEL: return [], 0, 0

    try:
        # -----------------------------------------------------------
        # [Step 1] 로컬 코드와 동일한 전처리 파이프라인
        # -----------------------------------------------------------
        
        # 1. 무조건 RGB 변환 (로컬 코드: if im.mode != "RGB": im = im.convert("RGB"))
        # (투명 배경 처리 로직도 굳이 넣지 않습니다. 로컬 코드가 그냥 convert('RGB')로 잘 됐다면 그게 정답입니다.)
        if im.mode != "RGB":
            im = im.convert("RGB")

        # 2. [핵심 복구] AutoContrast 적용
        # 파일이 62MB 원본이므로, 이제 이 기능은 '독'이 아니라 '약'이 됩니다.
        # 위성 사진의 대비를 높여 비행기를 선명하게 만듭니다.
        im_proc = ImageOps.autocontrast(im, cutoff=1)
        
        # -----------------------------------------------------------
        # [Step 2] 타일링 및 탐지 (로컬 설정값 완벽 준수)
        # -----------------------------------------------------------
        W, H = im.size
        TILE_SIZE = 1280  # 로컬 코드 값
        STRIDE = 1000     # 로컬 코드 값
        
        all_dets = []
        
        x_steps = list(range(0, W - TILE_SIZE, STRIDE))
        if (W - TILE_SIZE) % STRIDE != 0: x_steps.append(max(0, W - TILE_SIZE))
        if not x_steps and W <= TILE_SIZE: x_steps = [0]
            
        y_steps = list(range(0, H - TILE_SIZE, STRIDE))
        if (H - TILE_SIZE) % STRIDE != 0: y_steps.append(max(0, H - TILE_SIZE))
        if not y_steps and H <= TILE_SIZE: y_steps = [0]
        
        for y in y_steps:
            for x in x_steps:
                # 3. 크롭 (PIL Image 그대로 사용)
                crop = im_proc.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
                
                # 4. 예측 (로컬과 동일한 conf=0.35)
                # BGR 변환 같은 건 하지 않습니다. 로컬에서도 안 했으니까요.
                results = DET_MODEL.predict(crop, conf=0.35, verbose=False, imgsz=TILE_SIZE)
                
                if not results: continue
                
                for r in results:
                    if r.boxes is None: continue
                    for box in r.boxes:
                        bx1, by1, bx2, by2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        
                        gx1, gy1 = bx1 + x, by1 + y
                        gx2, gy2 = bx2 + x, by2 + y
                        
                        # 타일 경계선 노이즈 제거 (로컬 로직)
                        if (bx2 - bx1) < TILE_SIZE * 0.98 and (by2 - by1) < TILE_SIZE * 0.98:
                            all_dets.append((gx1, gy1, gx2, gy2, conf, cls))
                            
        final_parsed = []
        if len(all_dets) > 0:
            dets_arr = np.array(all_dets)
            keep_idxs = py_cpu_nms(dets_arr, 0.45)
            
            final_dets = dets_arr[keep_idxs]
            for i, d in enumerate(final_dets):
                x1, y1, x2, y2, conf, cls = d
                label = DET_MODEL.names[int(cls)]
                final_parsed.append([x1, y1, x2, y2, label, conf, i, 'STATIC'])
                
        return final_parsed, W, H
        
    except Exception as e:
        print(f"Det Error: {e}")
        return [], 0, 0

def run_detection_and_compare(path_t1, path_t2):
    dets1, w1, h1 = cached_detection(path_t1)
    dets2, w2, h2 = cached_detection(path_t2)
    import copy
    d1_copy = copy.deepcopy(dets1) if dets1 else []
    d2_copy = copy.deepcopy(dets2) if dets2 else []
    for i, d1 in enumerate(d1_copy):
        match = False
        for d2 in d2_copy:
            if get_center_dist(d1[:4], d2[:4]) < 60: match = True; break
        if not match: d1_copy[i][7] = 'VANISHED'
    for i, d2 in enumerate(d2_copy):
        match = False
        for d1 in d1_copy:
            if get_center_dist(d2[:4], d1[:4]) < 60: match = True; break
        if not match: d2_copy[i][7] = 'NEW'
    return d1_copy, w1, h1, d2_copy, w2, h2

def run_classification(crop_img):
    if not CLS_MODEL: return {"cls_top1": "-", "cls_conf": "-", "cls_top5": []}
    try:
        w, h = crop_img.size
        if w == 0 or h == 0: return {"cls_top1": "Error", "cls_conf": "-", "cls_top5": []}
        crop_img = crop_img.resize((w*2, h*2), Image.LANCZOS)
        res = CLS_MODEL.predict(crop_img, verbose=False)
        probs = res[0].probs
        top5 = []
        for i in range(min(3, len(probs.top5))):
            idx = int(probs.top5[i])
            score = float(probs.top5conf[i])
            top5.append(html.Li(f"{CLS_MODEL.names[idx]}: {score*100:.1f}%"))
        top1_idx = int(probs.top1)
        return {"cls_top1": CLS_MODEL.names[top1_idx], "cls_conf": f"{float(probs.top1conf)*100:.1f}%", "cls_top5": top5}
    except Exception:
        return {"cls_top1": "Error", "cls_conf": "-", "cls_top5": []}

def create_figure(img_path, dets, selected_idx=None):
    # 1. [수정] get_safe_image_path -> load_image_from_path
    # S3 URL이나 로컬 경로 모두 처리 가능한 통합 로더를 사용합니다.
    im = load_image_from_path(img_path)
    
    fig = go.Figure()
    
    # 이미지가 없으면 빈 그래프 반환
    if not im:
        fig.add_annotation(text="이미지 데이터 없음", showarrow=False)
        fig.update_layout(xaxis={'visible':False}, yaxis={'visible':False})
        return fig

    # 원본 크기 변수 초기화
    orig_w, orig_h = 0, 0
    
    try:
        # load_image_from_path는 이미 PIL.Image 객체를 반환하므로 with open()이 필요 없습니다.
        # 원본 보호를 위해 복사본을 생성하여 리사이징합니다.
        im_display = im.copy()
        
        if im_display.mode != "RGB": 
            im_display = im_display.convert("RGB")
            
        # 1. 원본 크기 저장 (좌표계 유지를 위해 필수!)
        orig_w, orig_h = im_display.size
        
        # 2. 웹 표시용 해상도 조절 (QHD급 3000px)
        # 원본(62MB)을 그대로 Base64로 만들면 브라우저가 멈추므로 리사이징합니다.
        target_size = (3000, 3000)
        im_display.thumbnail(target_size, Image.LANCZOS)
        
        # 3. JPEG 압축하여 전송
        buffer = io.BytesIO()
        im_display.save(buffer, format="JPEG", quality=85) 
        
        encoded_image = base64.b64encode(buffer.getvalue()).decode()
        img_source = f"data:image/jpeg;base64,{encoded_image}"
            
    except Exception as e:
        print(f"이미지 처리 실패: {e}")
        return fig

    # [중요] 이미지는 축소했지만, 레이아웃 좌표는 '62MB 원본 크기'로 설정
    fig.add_layout_image(
        dict(
            source=img_source,
            xref="x", yref="y",
            x=0, y=0,
            sizex=orig_w,  # 원본 너비
            sizey=orig_h,  # 원본 높이
            sizing="stretch",
            opacity=1.0,
            layer="below"
        )
    )

    # 박스 그리기 (기존 로직 동일)
    for d in dets:
        x1, y1, x2, y2, label, conf, idx, status = d
        is_sel = (idx == selected_idx)
        
        if status == 'NEW':      base_color = '#ff4757'
        elif status == 'VANISHED': base_color = "#bddb4e"
        else:                      base_color = '#00d2d3'
        
        color = '#ffffff' if is_sel else base_color
        width = 3 if is_sel else 2
        fill = f"rgba(255, 71, 87, 0.2)" if status == 'NEW' else "rgba(0,0,0,0)"
        dash_style = 'dot' if status == 'VANISHED' else 'solid'

        fig.add_trace(go.Scatter(
            x=[x1, x2, x2, x1, x1], y=[y1, y1, y2, y2, y1],
            fill="toself", fillcolor=fill, 
            mode='lines', 
            line=dict(color=color, width=width, dash=dash_style),
            hoverinfo='text', text=f"{label} [{status}]", 
            customdata=[idx], showlegend=False
        ))
        
        if is_sel or status == 'NEW':
            fig.add_annotation(x=x1, y=y1, text=f"{label} {conf:.2f}", showarrow=False, yshift=-15, font=dict(color="white", size=12), bgcolor=base_color)

    # 축 범위도 원본 크기에 맞춤
    fig.update_xaxes(showgrid=False, range=[0, orig_w], visible=False)
    fig.update_yaxes(showgrid=False, range=[orig_h, 0], visible=False, scaleanchor="x")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), clickmode='event', dragmode='pan', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    
    return fig

# [최종 단순화: 지휘관님 요청대로 DB 값 그대로 더해서 출력]
def get_trend_data(mode='today', base_name='Sunan'):
    all_slots = [f"{h:02d}:00" for h in range(0, 24, 2)]
    
    # 1. 시나리오 모드 (오늘)
    if mode == 'today':
        query = """
        SELECT s.timestamp,
               (COALESCE(s.cnt_fighter, 0) + COALESCE(s.cnt_bomber, 0) + COALESCE(s.cnt_civil, 0) + COALESCE(s.cnt_transport, 0)) as total
        FROM tb_scenario s
        JOIN tb_scene sc ON s.scene_id = sc.scene_id
        WHERE sc.scene_name = :bn
          AND s.data_type = 'SCENARIO'
        ORDER BY s.timestamp ASC
        """
        df_db = run_query(query, params={'bn': base_name})
        
        if not df_db.empty:
            df_db['dt'] = pd.to_datetime(df_db['timestamp'])
            # Time-Shift: 날짜는 버리고 시간만 챙긴다 (예: 2026-05-01 12:00 -> 12:00)
            df_db['hour'] = df_db['dt'].dt.hour
            # 짝수 시간으로 내림 (13시 -> 12시)
            df_db['time'] = df_db['hour'].apply(lambda h: f"{h - (h % 2):02d}:00")
            
            # [단순화] 같은 시간대에 데이터가 여러 개면? -> '가장 큰 값(MAX)' 하나만 쓴다.
            # 이유: 12시에 3대, 4대, 5대 찍혔으면 그 중 가장 위협적인 '5대'를 보여주는 게 맞음.
            df_agg = df_db.groupby('time')['total'].max().reset_index()
            df_agg.rename(columns={'total': 'count'}, inplace=True)
        else:
            df_agg = pd.DataFrame(columns=['time', 'count'])

    # 2. 이력 모드 (과거)
    else:
        # 이 부분은 기존 로직 유지 (날짜 범위 검색)
        end_date = datetime.now().strftime("%Y-%m-%d 23:59:59")
        if mode == 'week':
            start_date = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00")
        elif mode == 'month':
            start_date = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d 00:00:00")
        elif mode == 'year':
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d 00:00:00")
        else:
            return pd.DataFrame({'time': all_slots, 'count': [0]*12})

        query = """
        SELECT s.timestamp,
               (COALESCE(s.cnt_fighter, 0) + COALESCE(s.cnt_bomber, 0) + COALESCE(s.cnt_transport, 0)) as total
        FROM tb_scenario s
        JOIN tb_scene sc ON s.scene_id = sc.scene_id
        WHERE sc.scene_name = :bn
          AND s.timestamp BETWEEN :start AND :end
          AND s.data_type = 'HISTORY'
        ORDER BY s.timestamp ASC
        """
        df_db = run_query(query, params={'bn': base_name, 'start': start_date, 'end': end_date})
        
        if not df_db.empty:
            df_db['dt'] = pd.to_datetime(df_db['timestamp'])
            df_db['hour'] = df_db['dt'].dt.hour
            df_db['time'] = df_db['hour'].apply(lambda h: f"{h - (h % 2):02d}:00")
            
            # 과거 데이터는 평균
            df_agg = df_db.groupby('time')['total'].mean().reset_index()
            df_agg.rename(columns={'total': 'count'}, inplace=True)
        else:
            df_agg = pd.DataFrame(columns=['time', 'count'])

    # 3. 빈 시간 채우기 (공통)
    df_base = pd.DataFrame({'time': all_slots})
    df_final = pd.merge(df_base, df_agg, on='time', how='left').fillna(0)
    
    if mode == 'today':
        df_final['count'] = df_final['count'].astype(int)
    else:
        df_final['count'] = df_final['count'].round(1)
        
    return df_final