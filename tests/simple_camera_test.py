#!/usr/bin/env python3
"""
简单的摄像头帧率测试脚本
双摄像头版本，同时测试RGB和IR摄像头
"""

import cv2
import time
import sys
import threading
from datetime import datetime

def test_dual_camera_framerate(rgb_path=None, ir_path=None, duration=30):
    """
    同时测试两个摄像头的帧率
    
    Args:
        rgb_path: RGB摄像头路径或索引
        ir_path: IR摄像头路径或索引
        duration: 测试持续时间（秒）
    """
    print(f"开始测试双摄像头，持续时间 {duration} 秒")
    
    # 默认摄像头路径
    if rgb_path is None:
        rgb_path = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._RGB_CAMERA_SN0008-video-index0'
    if ir_path is None:
        ir_path = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera_SN0001-video-index0'
    
    print(f"RGB摄像头: {rgb_path}")
    print(f"IR摄像头: {ir_path}")
    
    # 初始化摄像头
    rgb_cap = cv2.VideoCapture(rgb_path)
    # ir_cap = cv2.VideoCapture(ir_path, cv2.CAP_GSTREAMER)
    ir_cap = cv2.VideoCapture(ir_path)

    rgb_cap.set(cv2.CAP_PROP_FPS, 30)
    ir_cap.set(cv2.CAP_PROP_FPS, 30)


    print(f"[Camera] [FPS] {rgb_cap.get(cv2.CAP_PROP_FPS)}, {ir_cap.get(cv2.CAP_PROP_FPS)}")

    # 检查摄像头是否打开成功
    rgb_available = rgb_cap.isOpened()
    ir_available = ir_cap.isOpened()
    
    if not rgb_available and not ir_available:
        print("错误: 两个摄像头都无法打开")
        return False
    
    if not rgb_available:
        print("警告: RGB摄像头无法打开，仅测试IR摄像头")
    if not ir_available:
        print("警告: IR摄像头无法打开，仅测试RGB摄像头")
    
    # 设置摄像头参数
    if rgb_available:
        rgb_cap.set(cv2.CAP_PROP_FPS, 30)
        rgb_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        rgb_fps_setting = rgb_cap.get(cv2.CAP_PROP_FPS)
        rgb_width = int(rgb_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        rgb_height = int(rgb_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"RGB摄像头设置: {rgb_width}x{rgb_height} @ {rgb_fps_setting} FPS")
    
    if ir_available:
        ir_cap.set(cv2.CAP_PROP_FPS, 30)
        ir_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ir_fps_setting = ir_cap.get(cv2.CAP_PROP_FPS)
        ir_width = int(ir_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ir_height = int(ir_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"IR摄像头设置: {ir_width}x{ir_height} @ {ir_fps_setting} FPS")
    
    print("-" * 60)
    
    # 共享变量和锁
    rgb_frame_count = 0
    ir_frame_count = 0
    lock = threading.Lock()
    running = True
    start_time = time.time()
    
    def rgb_capture_thread():
        """RGB摄像头捕获线程"""
        nonlocal rgb_frame_count, running
        if not rgb_available:
            return
        
        while running:
            ret, frame = rgb_cap.read()
            if ret:
                with lock:
                    rgb_frame_count += 1
            else:
                time.sleep(0.001)  # 短暂休眠避免忙等
    
    def ir_capture_thread():
        """IR摄像头捕获线程"""
        nonlocal ir_frame_count, running
        if not ir_available:
            return
        
        while running:
            ret, frame = ir_cap.read()
            if ret:
                with lock:
                    ir_frame_count += 1
            else:
                time.sleep(0.001)  # 短暂休眠避免忙等
    
    # 启动捕获线程
    threads = []
    if rgb_available:
        rgb_thread = threading.Thread(target=rgb_capture_thread)
        rgb_thread.daemon = True
        rgb_thread.start()
        threads.append(rgb_thread)
    
    if ir_available:
        ir_thread = threading.Thread(target=ir_capture_thread)
        ir_thread.daemon = True
        ir_thread.start()
        threads.append(ir_thread)
    
    print("测试进行中...")
    last_display_time = start_time
    
    # 主循环 - 显示进度
    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # 检查是否超时
        if elapsed_time >= duration:
            running = False
            break
        
        # 每秒显示一次当前状态
        if current_time - last_display_time >= 1.0:
            with lock:
                current_rgb_frames = rgb_frame_count
                current_ir_frames = ir_frame_count
            
            rgb_fps = current_rgb_frames / elapsed_time if rgb_available and elapsed_time > 0 else 0
            ir_fps = current_ir_frames / elapsed_time if ir_available and elapsed_time > 0 else 0
            remaining_time = duration - elapsed_time
            progress = (elapsed_time / duration) * 100
            
            status_line = f"时间: {elapsed_time:.1f}s"
            if rgb_available:
                status_line += f" | RGB: {current_rgb_frames}帧 ({rgb_fps:.2f}FPS)"
            if ir_available:
                status_line += f" | IR: {current_ir_frames}帧 ({ir_fps:.2f}FPS)"
            status_line += f" | 剩余: {remaining_time:.1f}s | 进度: {progress:.1f}%"
            
            print(status_line)
            last_display_time = current_time
        
        time.sleep(0.1)
    
    # 等待线程结束
    for thread in threads:
        thread.join(timeout=1.0)
    
    # 计算结果
    end_time = time.time()
    actual_duration = end_time - start_time
    
    rgb_avg_fps = rgb_frame_count / actual_duration if rgb_available else 0
    ir_avg_fps = ir_frame_count / actual_duration if ir_available else 0
    
    print("-" * 60)
    print("测试完成！")
    print(f"实际测试时间: {actual_duration:.2f} 秒")
    
    if rgb_available:
        print(f"RGB摄像头结果:")
        print(f"  总帧数: {rgb_frame_count}")
        print(f"  平均帧率: {rgb_avg_fps:.2f} FPS")
        print(f"  理论帧数 (按30FPS): {30 * actual_duration:.0f}")
        print(f"  帧率达成率: {(rgb_avg_fps/30)*100:.1f}%")
    
    if ir_available:
        print(f"IR摄像头结果:")
        print(f"  总帧数: {ir_frame_count}")
        print(f"  平均帧率: {ir_avg_fps:.2f} FPS")
        print(f"  理论帧数 (按30FPS): {30 * actual_duration:.0f}")
        print(f"  帧率达成率: {(ir_avg_fps/30)*100:.1f}%")
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"dual_camera_test_{timestamp}.txt"
    
    with open(result_file, 'w') as f:
        f.write(f"双摄像头帧率测试结果\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"实际测试时间: {actual_duration:.2f} 秒\n")
        f.write(f"RGB摄像头路径: {rgb_path}\n")
        f.write(f"IR摄像头路径: {ir_path}\n")
        f.write("-" * 50 + "\n")
        
        if rgb_available:
            f.write(f"RGB摄像头结果:\n")
            f.write(f"  分辨率: {rgb_width}x{rgb_height}\n")
            f.write(f"  设定FPS: {rgb_fps_setting}\n")
            f.write(f"  总帧数: {rgb_frame_count}\n")
            f.write(f"  平均帧率: {rgb_avg_fps:.2f} FPS\n")
            f.write(f"  帧率达成率: {(rgb_avg_fps/30)*100:.1f}%\n")
            f.write("\n")
        else:
            f.write(f"RGB摄像头: 不可用\n\n")
        
        if ir_available:
            f.write(f"IR摄像头结果:\n")
            f.write(f"  分辨率: {ir_width}x{ir_height}\n")
            f.write(f"  设定FPS: {ir_fps_setting}\n")
            f.write(f"  总帧数: {ir_frame_count}\n")
            f.write(f"  平均帧率: {ir_avg_fps:.2f} FPS\n")
            f.write(f"  帧率达成率: {(ir_avg_fps/30)*100:.1f}%\n")
        else:
            f.write(f"IR摄像头: 不可用\n")
    
    print(f"结果已保存到: {result_file}")
    
    # 清理资源
    if rgb_available:
        rgb_cap.release()
    if ir_available:
        ir_cap.release()
    cv2.destroyAllWindows()
    
    return True

def main():
    """主函数"""
    print("双摄像头帧率测试工具")
    print("=" * 60)
    
    # 默认参数
    duration = 30
    rgb_path = None
    ir_path = None
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
            if duration <= 0:
                raise ValueError()
        except ValueError:
            print("警告: 测试时间无效，使用默认值30秒")
            duration = 30
    
    if len(sys.argv) > 2:
        rgb_path = sys.argv[2]
    
    if len(sys.argv) > 3:
        ir_path = sys.argv[3]
    
    print(f"测试时间: {duration} 秒")
    if rgb_path:
        print(f"RGB摄像头路径: {rgb_path}")
    else:
        print("RGB摄像头路径: 使用默认路径")
    
    if ir_path:
        print(f"IR摄像头路径: {ir_path}")
    else:
        print("IR摄像头路径: 使用默认路径")
    
    print("-" * 60)
    
    # 运行测试
    success = test_dual_camera_framerate(rgb_path, ir_path, duration)
    
    if success:
        print("测试完成！")
        return 0
    else:
        print("测试失败！")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"发生错误: {e}")
        sys.exit(1)
