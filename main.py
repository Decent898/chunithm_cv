import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 

import cv2
import mediapipe as mp
import time
import pydirectinput 

# --- 核心配置 ---
ENABLE_INPUT = True 
pydirectinput.PAUSE = 0 
pydirectinput.FAILSAFE = False 

# ==========================================
#  画面与范围调整 (请根据实际情况修改)
# ==========================================
CAMERA_INDEX = 1

# 1. 旋转设置
# 如果你的摄像头是竖着装的，需要旋转画面让它变横
# None = 不旋转
# cv2.ROTATE_90_CLOCKWISE = 顺时针转90度
# cv2.ROTATE_90_COUNTERCLOCKWISE = 逆时针转90度
# ROTATE_TYPE = cv2.ROTATE_90_CLOCKWISE 
ROTATE_TYPE = None 

# 2. 判定范围收窄 (Region of Interest)
# 0.0 = 最左边, 1.0 = 最右边
# 例如 0.15 和 0.85 意味着左右各留 15% 的死区
ROI_X_MIN = 0.25
ROI_X_MAX = 0.75

# 防抖帧数
DEBOUNCE_FRAMES = 1

print("=" * 50)
print("✓ 启动中... (竖屏处理 + 窄范围模式)")
print("=" * 50 + "\n") 

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

SLIDER_KEYS = 16
AIR_THRESHOLD = 0.60

# 手指阈值
FINGER_CONFIG = {
    8:  {'name': 'Index',  'threshold': 0.75}, 
    12: {'name': 'Middle', 'threshold': 0.78}, 
    16: {'name': 'Ring',   'threshold': 0.75}
}

KEY_MAPPING = {
    0: 'l',  1: 'k',  2: 'j',  3: 'i',
    4: 'h',  5: 'g',  6: 'f',  7: 'e',
    8: 'd',  9: 'c',  10: 'b', 11: 'a',
    12: '9', 13: '8', 14: '7', 15: '6'
}
AIR_KEY = 'space' 

cap = cv2.VideoCapture(CAMERA_INDEX)
# 尝试设置高分辨率，旋转后会更清晰
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

key_timers = {} 
air_timer = 0
last_active_keys = set()
last_active_air = False

with mp_hands.Hands(
    max_num_hands=2,
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.8) as hands: 

    while cap.isOpened():
        success, image = cap.read()
        if not success: continue

        # --- 1. 画面旋转处理 ---
        if ROTATE_TYPE is not None:
            image = cv2.rotate(image, ROTATE_TYPE)

        # 镜像翻转（左右翻转，使画面符合直觉，如同照镜子）
        image = cv2.flip(image, 1)

        image.flags.writeable = False
        results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        image.flags.writeable = True

        h, w, c = image.shape
        
        # --- 2. 绘制辅助线 ---
        
        # (A) ROI 左右边界线 (蓝色粗线) - 你的手必须在这个范围内才有效
        roi_left_px = int(w * ROI_X_MIN)
        roi_right_px = int(w * ROI_X_MAX)
        cv2.line(image, (roi_left_px, 0), (roi_left_px, h), (255, 0, 0), 3)
        cv2.line(image, (roi_right_px, 0), (roi_right_px, h), (255, 0, 0), 3)

        # (B) 触摸阈值线 (绿色)
        base_thresh = FINGER_CONFIG[8]['threshold']
        cv2.line(image, (0, int(h * base_thresh)), (w, int(h * base_thresh)), (0, 255, 0), 2)
        
        # (C) 键位分割线 (只在 ROI 范围内画)
        roi_width = roi_right_px - roi_left_px
        for i in range(1, SLIDER_KEYS):
            # 这里的比例是相对于 ROI 的，不是全屏
            offset = int(roi_width * (i / SLIDER_KEYS))
            x_pos = roi_left_px + offset
            cv2.line(image, (x_pos, int(h * base_thresh)), (x_pos, h), (0, 255, 255), 1)

        raw_keys_this_frame = set()
        raw_air_this_frame = False

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                # Air 判定 (全屏有效，不受 ROI 限制)
                wrist = hand_landmarks.landmark[0] 
                if wrist.y < AIR_THRESHOLD:
                    raw_air_this_frame = True
                    cv2.putText(image, "AIR!", (int(wrist.x*w), int(wrist.y*h)-20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

                # Ground 判定 (必须在 ROI 范围内)
                for tip_id, config in FINGER_CONFIG.items():
                    tip = hand_landmarks.landmark[tip_id]    
                    pip = hand_landmarks.landmark[tip_id - 2]
                    
                    # 基础判定：低于阈值 + 手指伸直
                    is_pressing = tip.y > config['threshold'] and tip.y > pip.y + 0.02
                    
                    # === 核心修改：判定 X 是否在 ROI 范围内 ===
                    in_range = ROI_X_MIN < tip.x < ROI_X_MAX
                    
                    if is_pressing and in_range:
                        # 归一化计算：把 (ROI_MIN ~ ROI_MAX) 映射到 (0 ~ 1)
                        normalized_x = (tip.x - ROI_X_MIN) / (ROI_X_MAX - ROI_X_MIN)
                        
                        key_index = int(normalized_x * SLIDER_KEYS)
                        key_index = max(0, min(key_index, SLIDER_KEYS - 1))
                        
                        raw_keys_this_frame.add(key_index)
                        
                        # 视觉反馈
                        cv2.circle(image, (int(tip.x*w), int(tip.y*h)), 15, (0, 255, 0), -1)
                    elif is_pressing and not in_range:
                        # 虽然按下了，但在范围外 -> 画灰色点提示
                        cv2.circle(image, (int(tip.x*w), int(tip.y*h)), 10, (100, 100, 100), -1)

        # --- 3. 状态管理与输入 (保持防抖逻辑) ---
        
        # 更新计时器
        for k in raw_keys_this_frame:
            key_timers[k] = DEBOUNCE_FRAMES
            
        active_keys_stable = set()
        keys_to_delete = []
        for k in key_timers:
            if key_timers[k] > 0:
                active_keys_stable.add(k)
                key_timers[k] -= 1
            else:
                keys_to_delete.append(k)
        for k in keys_to_delete: del key_timers[k]

        if raw_air_this_frame: air_timer = DEBOUNCE_FRAMES
        is_air_stable = air_timer > 0
        if air_timer > 0: air_timer -= 1

        # 显示文本
        status_text = "KEYS: " + " ".join(map(str, sorted(list(active_keys_stable))))
        cv2.putText(image, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 硬件输入
        if ENABLE_INPUT:
            keys_to_press = active_keys_stable - last_active_keys
            for k in keys_to_press:
                if k in KEY_MAPPING: pydirectinput.keyDown(KEY_MAPPING[k])
            
            keys_to_release = last_active_keys - active_keys_stable
            for k in keys_to_release:
                if k in KEY_MAPPING: pydirectinput.keyUp(KEY_MAPPING[k])

            if is_air_stable and not last_active_air:
                pydirectinput.keyDown(AIR_KEY)
            elif not is_air_stable and last_active_air:
                pydirectinput.keyUp(AIR_KEY)

        last_active_keys = active_keys_stable
        last_active_air = is_air_stable

        cv2.imshow('Chunithm CV Controller (Rotated)', image)
        if cv2.waitKey(1) & 0xFF == 27: break

cap.release()
cv2.destroyAllWindows()