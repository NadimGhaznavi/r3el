---
title: "运行时行为"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-runtime-behaviour
permalink: /zh-CN/pages/runtime-behaviour/
---

[返回文档目录](/zh-CN/)

# 运行时行为

正常启动服务时，如果已配置模型 URL，就会恢复中断的处理。工作区为空、批次已完成或用户明确要求停止时，服务保持空闲。仅打开 Control 页面**不会**创建新批次。

**New Batch** 首先选择普通文件，每组最多处理 10 个。处理完这些文件后，再从源目录的直接子目录中寻找符合条件的目录，以填满批次剩余容量。目录内容递归扫描，但嵌套子目录不作为独立批次选择。每个目录条目都会先完成识别、匹配和导入，再处理下一个。

TMDB 结果选择、目录保存、媒体和 SRT 字幕移动、重复文件处理及源目录清理均已实现。工作进程独立于浏览器刷新运行。未解决的条目会保留供人工查看；不符合模式的目录保持原样。已完成批次会一直显示，直到被替换或清除。

**Stop Batch** 请求在当前操作结束后协作停止。**Clear Current Batch** 等待处理停止，然后只移除工作区记录。在 Action 列中，**TMDB ID** 和 **Replace Local Media** 提供受支持的人工更正操作；不存在操作下拉框或 Process Batch 按钮。

显式诊断模式 `--run-batch` 只运行识别，不执行正常的自动匹配与导入流程。

另请参阅[批次流程图](/zh-CN/pages/flowchart/)、[目录模式](/zh-CN/pages/directory-patterns/)、[导入及清理](/zh-CN/pages/import-cleanup/)和[持久化工作区](/zh-CN/pages/file-states/)。
