# HealthMirror - 智能健康镜系统

一个基于计算机视觉和心电图(ECG)的实时健康监测系统，能够通过摄像头进行非接触式生理参数检测，结合ECG模块实现多模态健康监测。

## 🎯 项目特色

- **非接触式心率检测**: 使用PhysNet和Step模型进行基于摄像头的心率检测
- **多模态监测**: 结合RGB摄像头、红外摄像头和ECG模块
- **实时处理**: 支持实时数据采集、处理和分析
- **蓝牙通信**: 支持通过蓝牙与移动设备通信
- **数据管理**: 完整的患者数据管理和存储系统
- **外设管理**: 集成显示屏、电池监测等外设

## 🏗️ 系统架构

```
HealthMirror/
├── main.py              # 主程序入口和核心控制逻辑
├── global_vars.py       # 全局变量定义
├── requirements.txt     # 依赖库清单
├── spp_protocol.md      # 蓝牙通信协议文档
├── bluetooth/           # 蓝牙通信模块
│   ├── listen.py        # 蓝牙监听服务
│   ├── spp.py           # 串口蓝牙协议
│   └── base.py          # 蓝牙基类
├── capture/             # 摄像头捕获模块
│   ├── camera.py        # 摄像头控制
│   └── base.py          # 捕获基类
├── model/               # AI模型模块
│   ├── physnet.py       # PhysNet心率检测模型
│   ├── step.py          # Step模型
│   └── base.py          # 模型基类
├── preprocess/          # 数据预处理模块
│   ├── mp.py            # MediaPipe人脸检测预处理
│   └── base.py          # 预处理基类
├── ecg/                 # ECG心电图模块
│   ├── ecg.py           # ECG数据处理
│   ├── bmd101.py        # BMD101 ECG传感器驱动
│   └── base.py          # ECG基类
├── log/                 # 数据日志模块
│   ├── dlog.py          # 数据日志记录
│   ├── plog.py          # 图片日志记录
│   ├── merge.py         # 日志合并
│   └── normalize.py     # 数据标准化
├── display/             # 显示模块
├── network/             # 网络模块
│   ├── wifi.py          # WiFi管理
│   └── uploader.py      # 数据上传
├── peripherals/         # 外设模块
├── peripheralmanager/   # 外设管理器
├── utils/               # 工具类
├── data/                # 数据存储目录
│   ├── patient_id_counter.txt
│   └── patient_XXXXXX/  # 患者数据目录
│       ├── patient_info.txt
│       ├── ecg_log.csv
│       ├── rppg_log.csv
│       ├── merged_log.csv
│       ├── normalized_log.csv
│       ├── video.mp4
│       ├── ir_video.mp4
│       ├── images/
│       └── ir_images/
└── rPPG-local-inference-main/  # rPPG推理模块
```

## 📋 系统要求

### 硬件要求
- Orange Pi 或类似的ARM开发板
- RGB摄像头 (USB连接)
- 红外摄像头 (USB连接)
- BMD101 ECG传感器模块
- 显示屏模块
- 蓝牙模块
- 电池管理模块

### 软件要求
- Python 3.9+
- OpenCV
- MediaPipe
- ONNX Runtime
- NumPy, SciPy
- Bluetooth相关库

## 🚀 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install -r requirements.txt

# 配置摄像头设备路径
# 编辑main.py中的摄像头路径
rgb_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._RGB_CAMERA_SN0008-video-index0'
ir_cam = '/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera_SN0001-video-index0'
```

### 2. 运行系统

```bash
# 启动主程序
python main.py
```

### 3. 蓝牙配置

参考 `spp_protocol.md` 进行蓝牙通信配置。

## 💡 核心功能

### 1. 心率检测
- **PhysNet模型**: 基于深度学习的心率检测
- **Step模型**: 另一种心率检测算法选择
- **ECG模块**: 传统心电图心率检测
- **多模态融合**: 结合摄像头和ECG数据

### 2. 数据采集
- **实时采集**: 30fps视频采集和实时ECG数据
- **多摄像头**: 同时支持RGB和红外摄像头
- **数据同步**: 时间戳同步确保数据一致性

### 3. 数据处理
- **人脸检测**: 使用MediaPipe进行人脸区域检测
- **信号处理**: 带通滤波、降噪等预处理
- **质量监测**: ECG信号质量实时评估

### 4. 患者管理
- **会话管理**: 自动生成患者ID和数据目录
- **数据存储**: 完整的患者数据记录和管理
- **数据导出**: 支持CSV格式数据导出

## 📱 蓝牙通信协议

系统支持通过蓝牙与移动设备进行通信，主要功能包括：

- **时间同步**: 设备时间同步
- **开始/停止采集**: 远程控制数据采集
- **设备信息**: 电池电量、存储空间等状态信息
- **WiFi配置**: 远程配置网络连接

详细协议请参考 `spp_protocol.md`。

## 🔧 配置说明

### 主要配置参数

```python
# 模型选择
model_choice = "Step"  # 或 "PhysNet"

# 摄像头配置
rgb_cam = '/dev/v4l/by-id/...'  # RGB摄像头路径
ir_cam = '/dev/v4l/by-id/...'   # 红外摄像头路径

# ECG配置
ecg_config = {
    "bmd101": {"serial_port": "/dev/ttyS0"},
    "max_queue_size": 512,
}

# 数据采集配置
time_limit = 60  # 采集时长(秒)
fps = 30         # 采集帧率
```

## 📊 数据格式

### ECG数据格式
```csv
timestamp,ecg_value,quality_flag
1749976367.721268,3056.0,0
```

### rPPG数据格式
```csv
timestamp,rppg_value,quality_flag
1749976367.722407,3223.0,0
```

### 合并数据格式
```csv
timestamp,signal_value,data_type
1749976367.721268,3056.0,0  # 0=ECG, 1=rPPG
```

## 🧪 测试工具

- `cv_test.py`: 摄像头参数测试
- `ser_test.py`: 串口通信测试
- `bluetooth_setup.py`: 蓝牙配置测试

## 📈 性能优化

- **多线程处理**: 采集、处理、显示分离
- **队列管理**: 高效的数据缓冲和传输
- **内存管理**: 定期垃圾回收避免内存泄漏
- **实时优化**: 针对嵌入式设备的性能优化

## 🤝 贡献指南

1. Fork 本项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 📄 许可证

本项目采用开源许可证，具体请查看 LICENSE 文件。

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 项目仓库: https://github.com/YukiChan1220/HealthMirror
- 问题报告: 请在 GitHub Issues 中提交

---

*本项目致力于推进非接触式健康监测技术的发展，为智能健康管理提供创新解决方案。*