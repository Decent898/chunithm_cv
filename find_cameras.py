import cv2
import time

def find_all_cameras():
    """查找并显示所有可用摄像头的索引"""
    print("=" * 50)
    print("摄像头检测工具")
    print("=" * 50)
    print("\n正在扫描摄像头设备...\n")
    
    available_cameras = []
    
    # 扫描前20个索引
    for i in range(20):
        print(f"检查索引 {i:2d}...", end=" ", flush=True)
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # 尝试读取一帧
                ret, frame = cap.read()
                if ret:
                    available_cameras.append(i)
                    print(f"✓ 摄像头可用")
                else:
                    print(f"✗ 无法读取")
                cap.release()
            else:
                print(f"✗ 无法打开")
        except Exception as e:
            print(f"✗ 错误: {e}")
    
    print("\n" + "=" * 50)
    if available_cameras:
        print(f"\n找到 {len(available_cameras)} 个可用摄像头:")
        print("-" * 50)
        for idx, camera_id in enumerate(available_cameras):
            print(f"  {idx + 1}. 摄像头索引: {camera_id}")
        print("-" * 50)
        print(f"\n推荐使用索引: {available_cameras[-1]} (最后一个，通常是虚拟摄像头)")
    else:
        print("\n未找到任何摄像头设备！")
    
    print("\n" + "=" * 50)
    return available_cameras

if __name__ == "__main__":
    cameras = find_all_cameras()
    
    # 允许用户选择并预览
    if cameras:
        while True:
            try:
                choice = input("\n输入要预览的摄像头索引 (或按 Enter 退出): ").strip()
                if not choice:
                    break
                
                camera_idx = int(choice)
                if camera_idx not in cameras:
                    print(f"错误: 索引 {camera_idx} 不可用")
                    continue
                
                print(f"\n正在打开摄像头 {camera_idx}...")
                cap = cv2.VideoCapture(camera_idx)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
                print("预览中... 按 'q' 退出预览")
                frame_count = 0
                start_time = time.time()
                
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    frame_count += 1
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    
                    # 显示帧率和索引信息
                    cv2.putText(frame, f"Camera Index: {camera_idx}", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 70), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    cv2.imshow(f"Camera {camera_idx}", frame)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                cap.release()
                cv2.destroyAllWindows()
                print(f"摄像头 {camera_idx} 已关闭\n")
                
            except ValueError:
                print("请输入有效的数字")
            except Exception as e:
                print(f"错误: {e}")
