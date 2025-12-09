import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import socket
import threading
import cv2
import mediapipe as mp
import time
import numpy as np
import pydirectinput

# =================配置区域=================
CAMERA_INDEX = 0   
ROTATE_TYPE = cv2.ROTATE_90_CLOCKWISE 
CAM_W, CAM_H = 640, 480

# 判定范围 (X轴)
ROI_X_MIN, ROI_X_MAX = 0.05, 0.95

# 【关键设置】Air 判定高度范围 (Y轴)
# 0.0=顶端, 1.0=底端
# 我们取下半屏：从 0.5 (中间) 到 1.0 (底部)
AIR_TOP_LIMIT = 0.5   # 判定区顶端 (IR6的上限)
AIR_BOTTOM_LIMIT = 1.0 # 判定区底端 (IR1的下限)

# 对应 sega.ini 的按键映射 (从下到上 IR1 -> IR6)
# 映射: m, n, o, p, q, r
IR_KEY_MAP = {
    1: 'm', 
    2: 'n', 
    3: 'o', 
    4: 'p', 
    5: 'q', 
    6: 'r'
}

MOTION_SENSITIVITY = 25 
MOTION_AREA_MIN = 500 

HOST_IP = '0.0.0.0' 
PORT = 3000

pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False
# =========================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Chuni Half-Screen IR</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        body { background: #000; overflow: hidden; color: #fff; font-family: monospace; user-select: none; }
        #status { position: fixed; top: 10px; left: 50%; transform: translateX(-50%); border: 1px solid #555; padding: 5px; background: rgba(0,0,0,0.5); pointer-events: none; z-index: 99; }
        #keyboard { display: flex; height: 100vh; width: 100vw; }
        .key { flex: 1; background: #111; box-shadow: inset 1px 0 0 0 rgba(255,255,255,0.1); touch-action: none; }
        .key:nth-child(4n) { box-shadow: inset 2px 0 0 0 rgba(255, 215, 0, 0.6); }
        .key.pressed { background: linear-gradient(to bottom, #00c6ff, #0072ff); }
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <div id="keyboard"></div>
    <script>
        try {
            const socket = io({ transports: ['websocket'], upgrade: false, reconnectionDelay: 1000 });
            const statusDiv = document.getElementById('status');
            const keyMap = ['l','k','j','i', 'h','g','f','e', 'd','c','b','a', '9','8','7','6'];
            
            keyMap.forEach(k => {
                let d = document.createElement('div'); d.className = 'key'; d.dataset.key = k;
                document.getElementById('keyboard').appendChild(d);
            });

            socket.on('connect', () => { statusDiv.textContent = "READY (Half-Screen IR)"; statusDiv.style.color = "#0f0"; });
            
            const currentHeldKeys = new Set();
            function updateVisuals() {
                document.querySelectorAll('.key').forEach(el => {
                    el.classList.toggle('pressed', currentHeldKeys.has(el.dataset.key));
                });
            }

            function handleTouch(e) {
                e.preventDefault(); 
                const newHeldKeys = new Set();
                const screenW = window.innerWidth;
                const keyWidth = screenW / 16;
                const edgeThreshold = keyWidth * 0.20; 

                Array.from(e.touches).forEach(t => {
                    let mainIndex = Math.floor(t.clientX / keyWidth);
                    if (mainIndex >= 0 && mainIndex < 16) {
                        newHeldKeys.add(keyMap[mainIndex]);
                        let offset = t.clientX % keyWidth;
                        if (offset < edgeThreshold && mainIndex > 0) newHeldKeys.add(keyMap[mainIndex - 1]);
                        if (offset > (keyWidth - edgeThreshold) && mainIndex < 15) newHeldKeys.add(keyMap[mainIndex + 1]);
                    }
                });

                newHeldKeys.forEach(k => { if (!currentHeldKeys.has(k)) socket.emit('keydown', k); });
                currentHeldKeys.forEach(k => { if (!newHeldKeys.has(k)) socket.emit('keyup', k); });
                currentHeldKeys.clear();
                newHeldKeys.forEach(k => currentHeldKeys.add(k));
                updateVisuals();
            }
            ['touchstart', 'touchmove', 'touchend', 'touchcancel'].forEach(evt => document.addEventListener(evt, handleTouch, {passive: false}));
            setInterval(() => { if (socket.connected) socket.emit('sync_keys', Array.from(currentHeldKeys)); }, 300);
        } catch(e) {}
    </script>
</body>
</html>
"""

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", max_decode_packets=500, async_mode='threading')

server_pressed_keys = set()
lock = threading.Lock()

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect(): print("✅ DEVICE CONNECTED!")

@socketio.on('keydown')
def handle_keydown(key):
    with lock:
        if key not in server_pressed_keys:
            pydirectinput.keyDown(key) 
            server_pressed_keys.add(key)

@socketio.on('keyup')
def handle_keyup(key):
    with lock:
        if key in server_pressed_keys:
            pydirectinput.keyUp(key)
            server_pressed_keys.remove(key)

@socketio.on('sync_keys')
def handle_sync(client_keys_list):
    client_keys = set(client_keys_list)
    with lock:
        stuck_keys = server_pressed_keys - client_keys
        for k in stuck_keys:
            pydirectinput.keyUp(k)
            server_pressed_keys.remove(k)

def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."): ips.append(ip)
    except: pass
    return ips

# --- 核心修改：下半屏 6 等分逻辑 ---
def get_ir_level(y_pos):
    # y_pos: 0.0 (顶) ~ 1.0 (底)
    
    # 1. 如果手太高 (超过中线)，视为未触发
    if y_pos < AIR_TOP_LIMIT: return 0 
    # 2. 如果手太低 (低于底线)，视为 IR1 (修正误差)
    if y_pos > AIR_BOTTOM_LIMIT: return 1
    
    # 3. 计算有效区域高度 (0.5)
    valid_height = AIR_BOTTOM_LIMIT - AIR_TOP_LIMIT
    
    # 4. 计算手距离底部的距离 (距离底部越远，IR等级越高)
    # distance_up: 0.0 (在底部) ~ 0.5 (在中间)
    distance_up = AIR_BOTTOM_LIMIT - y_pos
    
    # 5. 映射到 1-6
    # level = (distance_up / valid_height) * 6
    # +1 是因为 int 向下取整，我们需要 1-6
    level = int((distance_up / valid_height) * 6) + 1
    
    return max(1, min(6, level))

def run_camera_loop():   
    print("📷 Camera starting (Bottom-Half IR Mode)...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

    mp_hands = mp.solutions.hands
    
    active_ir_level = 0 
    last_ir_level = 0   
    debounce_frames = 2 
    debounce_timer = 0
    prev_gray = None

    with mp_hands.Hands(max_num_hands=2, model_complexity=0, min_detection_confidence=0.3, min_tracking_confidence=0.3) as hands:
        while cap.isOpened():
            success, image = cap.read()
            if not success: 
                time.sleep(0.01)
                continue

            if ROTATE_TYPE is not None: image = cv2.rotate(image, ROTATE_TYPE)
            
            h, w, c = image.shape
            
            # 这里的 air_y_threshold 设为中间线 (0.5)，用于动态检测范围
            mid_y = int(h * AIR_TOP_LIMIT)

            current_frame_level = 0 

            # ==========================================
            # 1. 动态检测 (计算重心 Y)
            # ==========================================
            # 只检测下半屏 (mid_y 到 h)
            roi_frame = image[mid_y:h, 0:w]
            gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            motion_y = -1 
            
            if prev_gray is not None:
                frame_delta = cv2.absdiff(prev_gray, gray)
                thresh = cv2.threshold(frame_delta, MOTION_SENSITIVITY, 255, cv2.THRESH_BINARY)[1]
                
                M = cv2.moments(thresh)
                if M["m00"] > MOTION_AREA_MIN: 
                    # 计算相对于 roi 的 cy
                    cy_roi = int(M["m01"] / M["m00"])
                    # 转换回全图坐标 (加上 mid_y 偏移)
                    cy_global = cy_roi + mid_y
                    
                    motion_y = cy_global / h 
                    
                    cx_roi = int(M["m10"] / M["m00"])
                    cv2.circle(image, (cx_roi, cy_global), 20, (255, 0, 0), 2)
            
            prev_gray = gray

            # ==========================================
            # 2. AI 检测 (手腕 Y)
            # ==========================================
            hand_y = -1
            image.flags.writeable = False
            results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            image.flags.writeable = True

            if results.multi_hand_landmarks:
                min_y = 1.0 # 找最高的手 (Y值最小)
                found = False
                for hl in results.multi_hand_landmarks:
                    wrist = hl.landmark[0]
                    # 必须在 X 范围内，且在下半屏 (y > 0.5)
                    if ROI_X_MIN < wrist.x < ROI_X_MAX and wrist.y > AIR_TOP_LIMIT:
                        if wrist.y < min_y:
                            min_y = wrist.y
                            found = True
                        cv2.circle(image, (int(wrist.x*w), int(wrist.y*h)), 15, (0, 255, 0), -1)
                if found: hand_y = min_y

            # ==========================================
            # 3. 融合判定
            # ==========================================
            final_y = -1
            if hand_y != -1: final_y = hand_y
            elif motion_y != -1: final_y = motion_y
            
            if final_y != -1:
                current_frame_level = get_ir_level(final_y)
            else:
                current_frame_level = 0

            # ==========================================
            # 绘制 UI 网格 (从中间画到底部)
            # ==========================================
            # 计算每层的高度 (像素)
            segment_px = (h - mid_y) / 6
            
            # 画顶部分界线 (蓝线)
            cv2.line(image, (0, mid_y), (w, mid_y), (255, 0, 0), 2)
            cv2.putText(image, "AIR LIMIT (50%)", (10, mid_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            for i in range(1, 7):
                # IR1 在最底下，IR6 在最上面(mid_y附近)
                # 计算每层线的 Y 坐标
                # IR6 的顶线是 mid_y
                # IR1 的顶线是 h - seg
                # 当前层的顶线:
                level_top_y = int(h - (i * segment_px))
                
                color = (0, 255, 255) if i == current_frame_level else (50, 50, 50)
                thickness = 2 if i == current_frame_level else 1
                
                cv2.line(image, (0, level_top_y), (w, level_top_y), color, thickness)
                # 文字画在线上方
                cv2.putText(image, f"IR{i}", (10, level_top_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # ==========================================
            # 4. 输入执行
            # ==========================================
            if current_frame_level > 0:
                active_ir_level = current_frame_level
                debounce_timer = debounce_frames
            elif debounce_timer > 0:
                debounce_timer -= 1
            else:
                active_ir_level = 0

            if active_ir_level != last_ir_level:
                if last_ir_level > 0:
                    pydirectinput.keyUp(IR_KEY_MAP[last_ir_level])
                if active_ir_level > 0:
                    new_key = IR_KEY_MAP[active_ir_level]
                    pydirectinput.keyDown(new_key)
                    print(f"IR{active_ir_level} ({new_key})")
            
            last_ir_level = active_ir_level

            cv2.imshow('Chuni Half-IR', image)
            if cv2.waitKey(1) & 0xFF == 27: break
    
    cap.release()
    cv2.destroyAllWindows()
    os._exit(0)

if __name__ == '__main__':
    ips = get_local_ips()
    print('\n' + '='*60)
    print('🚀 下半屏 6 分割模式 (Bottom to 50%)')
    print('⚠️  映射键: m, n, o, p, q, r')
    print('='*60)
    for ip in ips:
        print(f' 👉 http://{ip}:{PORT}')
    print('='*60 + '\n')

    t = threading.Thread(target=lambda: socketio.run(app, host=HOST_IP, port=PORT, debug=False))
    t.daemon = True
    t.start()
    
    try:
        run_camera_loop()
    except KeyboardInterrupt: pass
    except Exception as e: print(f"Error: {e}")
    finally:
        os._exit(0)