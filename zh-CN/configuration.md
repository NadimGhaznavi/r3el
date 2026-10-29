---
title: "CMDB 声明与运行时配置"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-configuration
permalink: /zh-CN/pages/configuration/
---

[返回文档目录](/zh-CN/)

R3el 在 `r3el/constants/DR3el.py` 中以字面量声明资产清单元数据。CMDB 读取该文件但不执行它。将应用登记为 `R3el`，重新扫描生产安装目录，即可发现版本及同机 MariaDB 目录。CMDB 尚未采集网络声明，但这些声明已描述默认监听器，并决定 R3el 的运行时默认值。

| 声明 | 用途 |
| --- | --- |
| `CMDB_DATABASES = (("R3el", "r3el"),)` | 本地 MariaDB 目录名称；安装、升级检查和移除按标签查询目录。 |
| `CMDB_NETWORK`，`http` | 控制 HTTP 监听器，默认 `0.0.0.0:42220`。 |
| `CMDB_NETWORK`，`backend` | 批处理服务器的 ZeroMQ 监听器，默认 `127.0.0.1:42221`，也是 Control 批处理客户端的目标。 |

数据库声明不保存密码或远程连接设置。运行时数据库凭据与连接选项仍由 `/etc/r3el/database.env` 提供。MariaDB 的出站端口和独立管理的共享 Qwen 服务使用各自的配置。匹配操作内部创建的临时 ZeroMQ 监听器继续使用动态端口。

## 生产环境监听器覆盖设置

安装程序仅在文件不存在时根据 `CMDB_NETWORK` 创建 `/opt/prod/r3el/conf/r3el.json`，重新安装或升级时保留现有内容。路径由 `DR3el.BASE_DIR` 决定。文件不含机密信息，服务账户可以读取。文件不存在时采用声明中的默认值，例如：

```json
{
  "network": {
    "http": {"interface": "127.0.0.1", "port": 43220},
    "backend": {"port": 43221}
  }
}
```

省略的监听器或字段沿用默认值。仅允许 `network`、已声明的用途以及 `interface` 和 `port` 字段。接口必须是 IPv4 地址字符串，端口必须是 1 至 65535 的整数。无效的 JSON 或设置会报告文件路径和字段；**不会**悄悄回退到默认配置。

`Configuration` 每个进程只解析一次设置。`Network.binding(use)` 返回绑定地址与端口；`Network.destination(use)` 为本地客户端将 `0.0.0.0` 转换为 `127.0.0.1`，其他明确地址保持不变。Control 连接批处理服务器时使用该本地目标。

Control 的 `--host`、`--port`、`--zmq-endpoint` 以及批处理服务器的 `--zmq-endpoint` 可在本次启动中覆盖配置。如果两个进程必须通信，就必须为双方指定相同的手工覆盖端点。

## 应用更改

编辑生产 JSON 文件，然后运行：

```sh
/opt/prod/r3el/scripts/services.sh restart
```

脚本会先验证配置，再停止任一服务，然后以新设置启动 Control 和批处理服务器。重启会中断正在处理的批次，所以只应在可以停止工作时执行。开始批处理前，共享 Qwen 服务必须已就绪。`services.sh start` 同样先验证配置。安装和升级操作也会在停止服务前验证设置，之后启动 Control，但保持批处理服务停止。

更改运行时覆盖设置不会修改 CMDB 中声明的默认资产清单。
