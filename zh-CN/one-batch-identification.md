---
title: "识别服务器"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-one-batch-identification
permalink: /zh-CN/pages/one-batch-identification/
---

[返回文档目录](/zh-CN/)

# 识别服务器

正常服务器会保持 MCP/ZeroMQ 监听，直到被停止。配置模型 URL 后，启动时恢复中断的任务；已完成或明确停止的批次保持空闲。

**New Batch** 将源目录、目的目录和批次大小发送给服务器，自动执行识别、TMDB 匹配、候选选择、目录保存及媒体移动。先按最多十个一组处理普通文件，再处理匹配的目录项。参见[批次流程](/zh-CN/pages/flowchart/)和[目录模式](/zh-CN/pages/directory-patterns/)。

显式 `--run-batch` 诊断流程只选取源目录下的普通文件，排除子目录和符号链接，识别文件名并退出。它可以重新载入保留的工作区，跳过已保存结果。仅识别并不会修改源文件；此诊断路径不运行正常的自动导入流程。

## 组件

工作流类位于 `r3el/app`，提示位于 `r3el/app/prompts`，MCP 工具位于 `r3el/app/tools`。stdio MCP 入口：`python -m r3el.app.tools`。

- `FileMgr` 是文件系统接口。
- `FileContext`、`SubmitIdentificationPrompt`、`InvalidIdentification` 分别提供任务上下文、工具指令及纠错反馈。
- `BatchIdentification` 和 `ToolConversation` 协调批次及单项对话。
- `LLM` 和 `IdentificationTools` 桥接 HTTP 和 stdio MCP；工具定义从 MCP 读取，并随模型请求提交。
- MCP 桥接器 `SubmitIdentification` 将数据经 ZeroMQ 转发。
- `SubmissionHandler` 和 `ValidateIdentification` 在 R3el 内验证普通表单，并返回识别结果或拒绝。
- `Identification` 保存片名、年份与 0–10 的整数置信度。
- `MediaFileBatch` 和 `MediaFile` 保存工作区数据。
- `WorkspaceDb` 通过共享 `DbMgr` 保存与重新加载工作区。

模型只提供**表单值**。批次、条目和尝试 ID 由 R3el 在模型控制范围之外生成。监听器通过尝试 ID 查找服务器持有的活跃上下文。

提供数据的提示采用 JSON 对象，在消息中分开设置 `instructions` 和 `data`。日期、文件名和验证原因始终保持结构化。TMDB 选择也使用相同格式，包括 `query` 对象及带有 `number`、`title`、`overview`、`vote_count` 的 `candidates` 数组。简介摘要会截取到约 160 字符后当前句子结束处；缺失简介时使用空字符串。只有说明文字的提示（如 `focus`）保留原文。

## 结果与日志

工作区状态和批次计数见[持久化工作区](/zh-CN/pages/file-states/)。

隐藏文件名（以 `.` 开头）标记为 `unresolved_hidden_file`，尝试次数为零，绝不提交给 LLM。它们仍占用批次名额，并出现在结果和事件日志中。

其他文件名先尝试一次，之后最多进行 `MAX_LLM_RETRIES = 2` 次纠正。无效工具调用结构或被拒绝的表单值会生成纠错提示。耗尽尝试后记录 `unresolved_llm`，并继续下一个文件。接受的提交状态是 `identified`，不代表已匹配 TMDB。提示和工具定义要求**0–10 的整数置信度**；浮点数、字符串、布尔值及越界数值都会被拒绝，不自动转换类型。

HTTP、MCP、数据库和传输故障会终止批次，不会悄悄当成识别失败重试。SIGTERM/SIGINT 取消当前对话，关闭 MCP 子进程和监听器，并停止服务器。

事件日志记录获得的文件名、提示来源与内容、原始模型响应、工具接收和结果、验证决定，以及单项/批次结果。JSON 中携带批次/条目/尝试 ID，条目 ID 即 `MediaFile` ID。父事件 ID 将批次、条目、尝试和工具事件连接起来。结果保存至 `media_file_batches` 和 `media_files`，写入事件日志，并以 JSON 输出；文件结果包含 `issues` 数组。

## 重启与工作区

每个文件结果与其完成事件在同一事务中提交。再次使用 `--run-batch` 会读取保留的批次并跳过已完成项目；中断文件重新开启识别对话。保存的目录、选择和批次大小优先于新传入的 `--film-dir` / `--batch-size`。同一工作区只能有一个处理器。恢复时记录 `batch_resumed`。

`identification_completed` 批次仍可供后续匹配与审查。重复执行 `--run-batch` 会直接返回已有结果而不调用模型。**Clear Current Batch** 在工作停止后删除工作记录，但保留媒体文件、媒体目录和事件历史。

安装和升级先应用 `EventSchema`，再应用 `WorkspaceSchema`，其中包含匹配生命周期状态。服务器 unit 从 `/etc/r3el/tmdb.env` 加载 TMDB 凭据用于自动匹配。

## 运行

从源代码运行时，安装依赖并设置 `DB_HOST`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`（`DB_PORT` 默认为 3306）。初始化两套数据库结构，然后连接 LlamaSrv 的默认推理端口：

```bash
.venv/bin/python -B -m r3el.activity.EventSchema
.venv/bin/python -B -m r3el.activity.WorkspaceSchema
.venv/bin/python -B -m r3el.server.R3elServer --run-batch --llm-url http://127.0.0.1:51001
```

可选的 `--film-dir`、`--batch-size` 和 `--zmq-endpoint` 覆盖 `DR3el` 默认值，默认批次大小为 10。隔离工作区应使用独立数据库。诊断 `--run-batch` 必须提供 `--llm-url` 或 `R3EL_LLM_URL`；仅启动空闲服务则不需要。

安装/升级准备 systemd 服务，但不会启动或启用开机自启。已安装的服务默认 `R3EL_LLM_URL` 为 `http://127.0.0.1:51001`，即 LlamaSrv 的默认推理地址，可由 `/etc/r3el/server.env` 覆盖。单独启动 LlamaSrv，等待 `http://127.0.0.1:51001/health`（或配置的模型地址）返回 HTTP 200，再启动空闲监听器：

```bash
sudo systemctl start r3el-server.service
```

若没有待恢复任务，服务等待新批次。只有明确使用 `--run-batch` 的诊断模式会在识别后退出；正常服务通过网页接收批次。

## LlamaSrv 模型服务

[LlamaSrv](https://llamasrv.osoyalce.com/)（[GitHub 仓库](https://github.com/NadimGhaznavi/llamasrv)）独立于 R3el 运行和管理本地 Qwen 模型。请先按照 LlamaSrv 的说明完成安装和模型准备。默认模型为 Qwen3.5-4B。应用向推理端口 `51001` 发送 OpenAI 兼容请求；端口 `51000` 用于 LlamaSrv 控制面板。R3el 在 `r3el/constants/DLlama.py` 中采用该公开默认值，不声明自己的模型监听器。

R3el 的安装、升级、卸载和 `scripts/services.sh` 只管理 R3el 服务，不会配置、启动、停止或删除 LlamaSrv、其账户/配置、llama.cpp 或模型文件。安装 R3el 或浏览媒体目录时可以停止模型；开始识别或通过 LLM 选择候选项之前，模型必须就绪。默认 LlamaSrv 安装使用：

```bash
sudo systemctl start llamasrv-llm.service
curl -fsS http://127.0.0.1:51001/health
```

等待 HTTP 200 后再启动 R3el 批处理服务器。若使用其他主机或推理端口，在 `/etc/r3el/server.env` 中设置 `R3EL_LLM_URL`；参见[模型连接配置](/zh-CN/pages/configuration/)。

保持 LlamaSrv 的 `llama.jinja` 启用（默认值），以向 llama-server 传递 `--jinja`。Qwen 模型需要支持工具的聊天模板；参见 [llama.cpp 函数调用文档](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)。R3el 启动自己的 stdio MCP 子进程，在每次请求中发送工具定义，执行返回的工具调用，并在需要纠正时回传工具结果。请求使用 `tool_choice: "required"` 和 `parallel_tool_calls: false`，期望获得一个带有 ID、函数名和 JSON 编码参数的结构化 `message.tool_calls` 条目。无需在 LlamaSrv 中注册 R3el 工具或设置 `--mcp-servers-config`。其他应用也可以通过同一模型服务提交并执行自己的工具。

升级旧版 R3el 后，新服务使用端口 `51001`，但 `/etc/r3el/server.env` 中的 `R3EL_LLM_URL` 覆盖值仍会保留。更新旧地址，或删除覆盖值以采用 LlamaSrv 默认地址。原先安装的 `qwen-server.service`、文件和账户保持不变。确认其他使用方后，再单独停用该旧服务。

## 验证

```bash
.venv/bin/python -B -m unittest discover -s tests -v
sudo env R3EL_TEST_DB=1 .venv/bin/python -B -m unittest discover -s tests -v
```

第二条命令需要通过 socket 获取 MariaDB root 权限，会创建/删除唯一的测试数据库及用户。测试使用临时文件名和模拟 LLM，不触碰生产文件或生产数据库。集成测试覆盖真实 HTTP、MCP、ZeroMQ、MariaDB，包括检查点回滚、排他处理和在批次中途强制终止服务器后的恢复。
