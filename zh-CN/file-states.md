---
title: "持久化工作区"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-file-states
permalink: /zh-CN/pages/file-states/
---

[返回文档目录](/zh-CN/)

# 持久化工作区

`MediaFileBatch` 管理当前批次；`MediaFile` 保存每个文件的当前工作数据。它们存储在 `media_file_batches` 和 `media_files` 中，因此处理可以跨服务重启恢复。

## MediaFile

| 字段 | 用途 |
| --- | --- |
| `id` | 供事件引用的稳定标识符。 |
| `path` | 文件路径（包括文件名）。 |
| `state` | 当前识别流程状态。 |
| `action` | 保存的预处理决定：`pending`、`approve`、`ignore` 或 `delete`。 |
| `identification` | 已接受的片名、年份和 0–10 的整数置信度。 |
| `issues` | 以 `{code, message}` 表示的当前问题；没有问题时为空。 |
| `attempts` | 获得当前结果时所使用的尝试次数。 |
| `tmdb_match` | 保存的查询、电影搜索结果、错误或跳过结果；匹配之前为 `null`。 |
| `retries` | TMDB 返回零结果后重新识别的次数，范围 0–3。 |

| 状态 | 含义 |
| --- | --- |
| `pending` | 等待识别。 |
| `identified` | LLM 识别已接受，但尚需 TMDB 匹配。 |
| `unresolved_llm` | 识别尝试已耗尽。 |
| `unresolved_hidden_file` | 隐藏文件名被跳过，未调用 LLM。 |

发现文件时状态为 `pending`；识别后转为其他三种结果之一。

## 预处理动作

`MediaFileAction` 与识别状态分开，保存在 `media_files.action`。新文件起始为 `pending`。当置信度等于 `DR3el.AUTO_APPROVE_CONFIDENCE`（10）时，识别检查点将动作设为 `approve`，否则为 `pending`。这一决定与文件结果、完成事件在同一事务中保存。

Control 页面不再显示 Action 下拉框，但保存的字段仍是流程协议的一部分：`pending` 和 `approve` 可继续匹配，`ignore` 和 `delete` 会被跳过。

匹配自动开始。单个 TMDB 结果直接确定电影；多个结果则由 LLM 根据候选编号、标题、剧情摘要和投票数选择。零结果最多触发三次重新识别，随后在年份前后各一年继续搜索。未解决的结果可通过 **TMDB ID** 人工指定。目标路径精确冲突时显示 **Entry exists**，并提供 **Replace Local Media**。

匹配流程保存媒体目录元数据并导入文件。`catalogue_saved` 和 `file_moved` 检查点将数据库提交与文件移动分开。界面使用 **Imported** 替换 Identified 标签，但内部识别状态仍是 `identified`。通过匹配结果和 Current Task 查看导入错误或尚未完成的工作。

目录行包含双文件识别所需的 `find_ls`；目录中的单部电影携带 `source_directory`，文件名缺少年份时也携带 `find_ls`。这样可以在重启后保留年份判断上下文。附件保存视频/SRT 关联和部分编号。有歧义的字幕被标为 `unresolved_srt`，留在源目录。参见[目录模式](/zh-CN/pages/directory-patterns/)和[导入与清理](/zh-CN/pages/import-cleanup/)。

## MediaFileBatch

保存 `id`、`requested_size`、`source_directory`、`destination_directory`、有序 `files`、`state` 和 `started_event_id`。工作区同一时间仅容纳一个批次。

| 状态 | 含义 |
| --- | --- |
| `processing` | 正在识别。 |
| `failed` | 因错误停止处理。 |
| `cancelled` | 用户停止处理；旧版本也用来表示服务停机。 |
| `identification_completed` | 诊断识别已完成，但没有自动导入。 |
| `matching` | 正在自动匹配 TMDB。 |
| `matching_completed` | 自动匹配完成，结果可供检查。 |
| `matching_failed` | 自动匹配因错误停止。 |

显式诊断命令 `--run-batch` 会恢复待处理文件，并将 `failed` / `cancelled` 批次变回 `processing`。识别完成并不等于整个流程结束。正常服务器启动从已保存的选择恢复中断的处理或匹配；完成的批次及显式 Stop Batch 请求保持空闲。没有停止请求的旧版 `cancelled` 批次也会继续。工作中断时 New Batch 不可用；从 Control 发起的新批次可替换已完成的工作区，不能替换正在处理的工作区。媒体目录和事件历史保留。批次会保存导入目的目录。

## 持久化和清理

- 实体负责数据，活动负责操作及状态转换。
- `WorkspaceDb` 通过 `DbMgr` 在识别前保存选中的文件，并将每个结果及完成事件一起提交。
- 诊断 `--run-batch` 使用已有选择，跳过保存的结果并重试中断文件。工作区只能由一个处理器占用。
- `issues` 表示当前问题，不是累积的清理历史。
- 仅完成识别的批次仍可查看，无须再次调用模型。
- New Batch 在提交新的选择时清除旧的工作记录，但保留正式媒体记录；事件日志的保留策略独立管理。

## 批次计数器

`batch_completed` 对 `MediaFile` 计数：`count` 为总数，`unresolved_llm` 和 `unresolved_hidden_file` 分别统计对应状态，包括零值。批次生命周期事件与文件状态分开。

参见[单批次识别](/zh-CN/pages/one-batch-identification/)。
