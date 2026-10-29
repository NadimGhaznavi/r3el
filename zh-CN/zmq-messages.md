---
title: "ZeroMQ 消息"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-zmq-messages
permalink: /zh-CN/pages/zmq-messages/
---

[返回文档目录](/zh-CN/)

# ZMQ 消息

R3el 在 `DR3el.CMDB_NETWORK` 解析出的 `backend` 监听端点上，使用每次请求/响应一个 JSON 帧的协议（默认 `tcp://127.0.0.1:42221`）。`ZMQMsg` 定义消息封装，`DZMQ` 定义协议版本与计时参数，`DMessage` 定义应用的发送方、目标、方法和控制响应常量。`MessageHandler` 将请求交给专用处理器。发送方名称只标识消息角色，**不构成身份认证凭据**。

## 创建批次

```json
{
  "protocol_version": 1,
  "sender": "r3el-control",
  "target": "batch",
  "method": "new_batch",
  "payload": {
    "input_directory": "/exports/disk1/archive/film",
    "output_directory": "/exports/disk1/archive/media/movies",
    "batch_size": 5
  }
}
```

`BatchControl` 发送该消息。`BatchControlHandler` 通过 `BatchConfiguration` 只验证这些参数：绝对目录路径、以及来自 `DR3el.BATCH_SIZES` 的整数批次大小（5、10、20、50 或 100）。处理开始时，R3el 服务必须能够读取输入目录。输出目录保留供后续文件操作使用，识别阶段不向其写入数据。

响应的发送方为 `r3el`，目标为 `r3el-control`，方法为 `new_batch`，`payload` 有以下情况：

- `{"status": "accepted"}`：已安排处理，但尚未完成。
- `{"status": "busy"}`：其他批次已预订或运行，没有创建新批次。
- `{"status": "error", "error": {"code": "invalid_parameters", "message": "..."}}`。
- `{"status": "error", "error": {"code": "not_configured"}}`：没有模型 URL，或者服务器处于诊断单批次模式。
- `{"status": "error", "error": {"code": "unknown_request"}}`：该命令不支持指定的路由或发送方。

`BatchProcessor` 预订唯一批次并将执行安排在应用事件循环中。`BatchRunner` 建立新的数据库连接并组装识别资源。监听线程继续接受工具提交。完成后处理器恢复空闲。预期的文件系统、HTTP 和数据库连接故障会被记录，并释放处理器；程序错误则继续传播。

此接口假定工作区为空，不提供替换或清理。New Batch 永远不会暗中复用或覆盖已有工作区。这类请求在执行时失败，并记录到服务日志。系统不会自动重试：如果接受响应丢失，**不能断定**批次没有启动。事件日志记录批次和条目的结果。

## 提交识别结果

MCP 使用发送方 `mcp-identification`、目标 `identification`、方法 `submit_identification`。`payload` 中包括 `attempt_id` 以及带有 `title`、`year`、`confidence` 的 `submission` 对象。`SubmissionHandler` 查找服务器持有的识别尝试，返回 `ok`、`rejected` 或 `error`。没有活跃尝试时，空闲服务器拒绝提交。现有 MCP 行为不变。

无效消息封装和传输处理器故障继续使用现有 `error` 响应，错误代码分别为 `invalid_request` 和 `handler_error`。
