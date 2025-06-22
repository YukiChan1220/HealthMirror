# 健康镜蓝牙接口
## 1 接口说明
接口采用 JSON 字符串格式，基本形式为：
```json
{"command":{"key1":"value1","key2":"value2",…}}
```
其中，command 是需要进行的操作命令，内层的键值对是该命令的参数。

## 2 接口定义
手机发送给终端的命令：
| 功能   | command        | 参数 (key)      | 参数说明                                     | 参数值示例                                                 | 参数类型   |
| ---- | -------------- | ------------- | ---------------------------------------- | ----------------------------------------------------- | ------ |
| 时间同步 | set\_time      | time          | Unix 时间戳                                 | `1715837562.215478`                                   | number |
| 开始采集 | start\_capture | patient\_info | 病人信息                                     | `"房颤，高血压"`                                            | string |
|      |                | time          | Unix 时间戳                                 | `1715837562.215478`                                   | number |
| 停止采集 | stop\_capture  | time          | Unix 时间戳                                 | `1715837562.215478`                                   | number |
| 刷新信息 | refresh\_info  | time          | Unix 时间戳                                 | `1715837562.215478`                                   | number |
| 配置网络 | config\_wifi   | ssid          | Wifi SSID                                | `"Tsinghua_Secure"`                                   | string |
|      |                | auth          | 身份验证方式                                   | `"OPEN"` / `"WPA2_PSK"` / `"EAP_PEAP"` / `"EAP_TTLS"` | string |
|      |                | username      | (若 `auth` 非 `"OPEN"` 或 `"WPA2_PSK"`) 用户名 | `"zhangsan24"`                                        | string |
|      |                | password      | (若 `auth` 非 `"OPEN"`) 密码                 | `"1234abcd"`                                          | string |
|      |                | time          | Unix 时间戳                                 | `1715837562.215478`                                   | number |
| 应答   | ack            | command       | 上一条命令                                    | `"set_time"`                                          | string |
|      |                | status        | 命令返回状态                                   | `"success"` / `"failure"` / `"unknown"`               | string |

终端发送给手机的命令：
| 功能   | command | 参数 (key)         | 参数说明       | 参数值示例                                   | 参数类型   |
| ---- | ------- | ---------------- | ---------- | --------------------------------------- | ------ |
| 刷新信息 | info    | device\_id       | 终端 ID      | `1`                                     | number |
|      |         | patient\_count   | 已采集病人数量    | `234`                                   | number |
|      |         | space\_remaining | 剩余存储空间(MB) | `4096`                                  | number |
|      |         | battery\_level   | 剩余电量       | `70`                                    | number |
| 应答   | ack     | command          | 上一条命令      | `"set_time"`                            | string |
|      |         | status           | 命令返回状态     | `"success"` / `"failure"` / `"unknown"` | string |

## 3 通信流程
### 3.1 同步设备时间
手机发送：
```json
{"set_time":{"time":1715837562.215478}}
```
终端返回：
```json
{"ack":{"command":"set_time","status":"success"}}
```

### 3.2 采集流程
手机发送：
```json
{"start_capture":{"patient_info":"房颤、高血压","time":1715837562.215478}}
```
终端返回：
```json
{"ack":{"command":"start_capture","status":"success"}}
```
手机发送停止命令：
```json
{"stop_capture":{"time":1715837562.215478}}
```
终端返回：
```json
{"ack":{"command":"stop_capture","status":"success"}}
```

### 3.3 设备信息刷新
手机发送：
```json
{"refresh_info":{"time":1715837562.215478}}
```
设备返回 ack：
```json
{"ack":{"command":"refresh_info","status":"success"}}
```
设备发送 info：
```json
{"info":{"device_id":1,"patient_count":234,"space_remaining":4096,"battery_level":70}}
```
手机返回 ack：
```json
{"ack":{"command":"info","status":"success"}}
```

### 3.4 配置设备网络
手机发送：
```json
{
  "config_wifi":{
    "ssid":"Tsinghua_Secure",
    "auth":"EAP_PEAP",
    "username":"zhangsan24",
    "password":"1234abcd",
    "time":1715837562.215478
  }
}
```
设备返回 ack：
```json
{"ack":{"command":"config_wifi","status":"success"}}
```
