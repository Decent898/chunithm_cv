# Chunithm Controller (CV + Touch)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-green?logo=flask)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-red?logo=opencv)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)

**Chunithm Hybrid Controller** 是一个创新的输入解决方案，旨在为 Chunithm 模拟器提供低延迟、高精度的混合控制体验。它巧妙地结合了 **iPad/平板** 的多点触控能力与 **Web 摄像头** 的空间手势识别，完美复刻了街机台的“触摸条”与“Air”空中判定。

经过测试，调教较好的环境能达到90%左右于正版手台的性能

---

## ✨ 核心特性 (Features)

-   **📱 零成本触控板**：利用 iPad 或任意触屏设备作为 16 键触摸条，支持多点触控、长按 (Hold) 与滑动 (Slide)。
-   **📷 6 段式 Air 判定**：使用 MediaPipe 手部追踪 + 光流法，将摄像头画面下半部分割为 6 个高度层级，分别触发 IR1-IR6，完美支持 Air 动作。
-   **⚡ 低延迟通讯**：基于 WebSocket (gevent/eventlet) 的局域网通讯，确保毫秒级响应，拒绝断触。
-   **🛡️ 智能防抖**：内置输入防抖算法，有效过滤摄像头噪点与误触。
-   **🔧 高度可配置**：支持自定义按键映射、摄像头旋转、判定区域 (ROI) 与灵敏度调节。

---

## 🛠️ 架构原理 (Architecture)

本项目由两个核心模块组成，协同工作以模拟完整的街机输入：

1.  **Web 触控端 (Flask + SocketIO)**：
    -   在电脑上运行 Web 服务器，iPad 通过局域网访问。
    -   iPad 屏幕被划分为 16 个触摸区域，实时捕获触摸事件并通过 WebSocket 发送至电脑。
    -   电脑端接收到信号后，使用 `pydirectinput` 模拟对应的键盘按键。

2.  **视觉识别端 (OpenCV + MediaPipe)**：
    -   后台运行摄像头捕捉循环。
    -   **6 段式高度检测**：将画面下半屏 (50%~100%) 垂直等分为 6 个区域。
    -   实时追踪手腕高度，根据手腕所在的区域触发对应的 IR 键 (IR1 ~ IR6)。
    -   **IR1 (最底层)** 对应按键 `m`，**IR6 (最高层)** 对应按键 `r`。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备

确保已安装 Python 3.10+，并以**管理员身份**运行 PowerShell（模拟全局按键需要权限）。

```powershell
# 进入项目目录
cd D:\Programming2\chunithm_cv

# 激活虚拟环境
& .\venv\Scripts\Activate.ps1

# 安装依赖
& .\venv\Scripts\pip.exe install -r requirements.txt
```

### 2. 启动控制器

```powershell
& .\venv\Scripts\python.exe webb.py
```

启动成功后，控制台将显示：
-   `📱 iPad 连接地址`: 例如 `http://192.168.1.x:3000`
-   `📷 Camera starting (Bottom-Half IR Mode)...`

### 3. 连接设备

-   **触控**: 确保 iPad 与电脑在同一局域网，使用 Safari 打开上述地址。
-   **Air**: 调整摄像头位置，确保能拍到手部动作。

---

## ⚙️ 配置文件详解 (Configuration)

为了让控制器与游戏完美配合，你需要理解并配置以下两个部分。

### 1. `webb.py` (控制器配置)

在 `webb.py` 顶部可以修改硬件参数与 Air 映射：

```python
CAMERA_INDEX = 0        # 摄像头设备索引
ROTATE_TYPE = cv2.ROTATE_90_CLOCKWISE # 画面旋转
AIR_TOP_LIMIT = 0.5     # Air 判定区顶端 (0.0-1.0)
AIR_BOTTOM_LIMIT = 1.0  # Air 判定区底端

# Air 键位映射 (IR1=最底层, IR6=最高层)
IR_KEY_MAP = {
    1: 'm', 2: 'n', 3: 'o', 4: 'p', 5: 'q', 6: 'r'
}
```

### 2. `segatools.ini` (游戏映射配置)

`segatools.ini` 是连接本项目与游戏本体的桥梁。本项目模拟的是**键盘按键**，因此必须确保 `segatools.ini` 中的映射与本项目的输出一致。

#### 🎮 触摸条映射 (`[slider]`)

本项目将 iPad 的 16 个按键映射为键盘上的 `6, 7, 8, 9, a, b, c, d, e, f, g, h, i, j, k, l`。
Chunithm 游戏有 32 个触摸传感器 (Cell)，通常每 2 个 Cell 对应 1 个物理按键。

**请确保你的 `segatools.ini` 中 `[slider]` 部分如下配置：**

> 注意：`segatools` 的 Cell 编号是从右向左的 (Cell 1 是最右侧)，而本项目的按键也是从右向左排列 (Key 16 是最右侧)。

```ini
[slider]
enable=1
; 对应 webb.py 的按键 '6' (0x36)
cell1=0x36
cell2=0x36
; 对应 webb.py 的按键 '7' (0x37)
cell3=0x37
cell4=0x37
; ... (中间省略，依次递增) ...
; 对应 webb.py 的按键 'l' (0x4C)
cell31=0x4c
cell32=0x4c
```

#### 👋 Air 映射 (`[ir]`)

本项目采用了 **6 段式独立 Air 判定**，因此需要在 `segatools.ini` 中启用 `[ir]` 并分别映射 6 个按键。

**请确保你的 `segatools.ini` 中 `[ir]` 部分如下配置：**

```ini
[io3]
; 禁用单键 Air 模式
ir=0

[ir]
enable=1
; IR1 (最底层) -> 对应 webb.py 的 'm' (0x4D)
ir1=0x4D
; IR2 -> 对应 webb.py 的 'n' (0x4E)
ir2=0x4E
; IR3 -> 对应 webb.py 的 'o' (0x4F)
ir3=0x4F
; IR4 -> 对应 webb.py 的 'p' (0x50)
ir4=0x50
; IR5 -> 对应 webb.py 的 'q' (0x51)
ir5=0x51
; IR6 (最高层) -> 对应 webb.py 的 'r' (0x52)
ir6=0x52
```

---

## 🔧 常见问题 (Troubleshooting)

| 问题现象 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| **网页无法连接** | 防火墙拦截 / IP 错误 | 检查 Windows 防火墙放行 3000 端口；确认使用局域网 IP。 |
| **按键长按断触** | 通讯模式降级 | 确保安装了 `gevent` 或 `eventlet` 以启用 WebSocket 模式。 |
| **Air 判定不灵敏** | 阈值/光线问题 | 调整 `AIR_TOP_LIMIT`；保证环境光线充足；调整摄像头角度。 |
| **游戏无反应** | 权限不足 / 映射错误 | **必须以管理员身份运行脚本**；检查 `segatools.ini` 映射是否匹配。 |

---

## 📜 开源协议

本项目基于 MIT 协议开源。
Powered by [Flask](https://flask.palletsprojects.com/), [MediaPipe](https://mediapipe.dev/), & [OpenCV](https://opencv.org/).
