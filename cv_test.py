import cv2

def list_available_cameras(max_index=10):
    """列出所有可用的摄像头索引。"""
    available_cameras = []
    print("[INFO] Scanning available cameras...")
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap is not None and cap.isOpened():
            print(f"[INFO] Found camera at index {index}")
            available_cameras.append(index)
            cap.release()
    if not available_cameras:
        print("[WARN] No cameras found.")
    return available_cameras

def test_camera_params(device_index=0):
    """测试并打印指定摄像头的参数信息。"""
    print(f"\n[INFO] Testing camera at index {device_index}...")
    cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)  # 明确使用 V4L2 后端
    if not cap.isOpened():
        print("[ERROR] Failed to open camera.")
        return

    print("[INFO] Camera opened successfully.")
    print("Backend used       :", cap.getBackendName())
    print("Frame Width        :", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("Frame Height       :", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("FPS                :", cap.get(cv2.CAP_PROP_FPS))
    print("FourCC (Pixel fmt) :", cap.get(cv2.CAP_PROP_FOURCC))

    # 解析 FourCC 编码格式
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print("Decoded FOURCC     :", fourcc_str)

    cap.release()

if __name__ == "__main__":
    # 第一步：列出可用摄像头
    cameras = list_available_cameras()
    print("\n[RESULT] Available camera indexes:", cameras)

    # 第二步：测试每个摄像头的参数
    for cam_index in cameras:
        test_camera_params(cam_index)
