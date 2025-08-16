#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_mjpg_support.py

快速检查 OpenCV 是否支持 480p MJPG 编码器写视频。

用法：
    python check_mjpg_support.py

如果支持，脚本会创建一个 test_mjpg.avi（1 秒，640x480，灰色帧），
并打印一些信息；如果不支持，会输出错误信息并退出。
"""

import cv2
import numpy as np
import os
import sys
import tempfile

def get_fourcc(codec: str) -> int:
    """
    把四字符编码转换为 OpenCV 能用的 FourCC 码。
    例：'MJPG' -> cv2.VideoWriter_fourcc('M','J','P','G')
    """
    if len(codec) != 4:
        raise ValueError("FourCC 需要 4 个字符")
    return cv2.VideoWriter_fourcc(*codec)

def can_write_mjpg():
    """检查是否能用 MJPG 编码器写 480p 视频。"""
    # 1. 创建临时文件名
    tmp_dir = tempfile.gettempdir()
    out_path = os.path.join(tmp_dir, "test_mjpg.avi")

    # 2. 定义视频参数
    fps = 30
    width, height = 640, 480   # 480p
    fourcc = get_fourcc('MJPG')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    # 3. 检查 VideoWriter 是否打开成功
    if not out.isOpened():
        print("[ERROR] VideoWriter 没有成功打开。")
        return False

    # 4. 写入 1 秒的帧（30 帧）
    for i in range(int(fps)):
        # 这里用一张 48% 亮度的灰色帧，保持简单
        frame = np.full((height, width, 3), 120, dtype=np.uint8)
        out.write(frame)

    out.release()

    # 5. 进一步验证文件是否可读
    # 仅检查文件是否存在且大小不为 0
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        print("[ERROR] 写入的文件不存在或为空。")
        return False

    # 6. 用 cv2 读取，确认能解码
    cap = cv2.VideoCapture(out_path)
    if not cap.isOpened():
        print("[ERROR] 读取测试文件失败，可能编码不支持。")
        return False

    # 读取帧数
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    print("[INFO] 成功写入 MJPG 视频！")
    print(f"    文件路径   : {out_path}")
    print(f"    维度      : {width}x{height}")
    print(f"    帧数      : {frame_count}")
    print(f"    编码方式  : MJPG")
    print(f"    文件大小  : {os.path.getsize(out_path)/1024:.1f} KB")
    return True

def main():
    print("=== 检查 OpenCV 是否支持 480p MJPG 编码 ===")
    print(f"OpenCV 版本: {cv2.__version__}")
    print("正在尝试写入 1 秒 480p MJPG 视频…")
    if can_write_mjpg():
        print("\n✅ 你的环境支持 MJPG 编码（480p）。")
    else:
        print("\n❌ 你的环境不支持 MJPG 编码或写入失败。")
        print("建议检查:")
        print("  * OpenCV 是否链接到 ffmpeg / gstreamer")
        print("  * 系统是否安装了 MJPG 编解码器")
        print("  * 其它编解码器（如 XVID、H264）是否可用")
        sys.exit(1)

if __name__ == "__main__":
    main()
