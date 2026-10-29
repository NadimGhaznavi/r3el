---
title: "导入与源目录清理"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-import-cleanup
permalink: /zh-CN/pages/import-cleanup/
---

[返回文档目录](/zh-CN/) · [批次流程](/zh-CN/pages/flowchart/) · [目录模式](/zh-CN/pages/directory-patterns/)

单个 TMDB 匹配、已接受的 LLM 选择或手工输入的 TMDB ID 都可以确定待导入电影。目标名称取自 TMDB 记录中的片名和上映年份。

```mermaid
flowchart TD
    Resolved["电影已确认"] --> Details["获取电影详情并应用格式优先级"]
    Details --> Existing{"优先格式的电影已登记？"}
    Existing -->|是，新文件格式较差| Duplicate["保留现有媒体；检查点之后删除低优先级副本"]
    Existing -->|否，或新格式更优| Names["为目标视频及关联 SRT 命名"]
    Names --> Conflict{"目标文件发生冲突？"}
    Conflict -->|是，未授权替换| Entry["Entry exists：保留源文件；提供 Replace Local Media"]
    Entry -->|用户请求替换| Names
    Conflict -->|否，或已授权| Stage["在同一文件系统建立临时硬链接；准备图片"]
    Stage --> Commit["提交媒体目录、路径和工作区检查点"]
    Commit --> Inodes["检查源与目标的 inode 是否相同"]
    Inodes --> Remove["移除源文件名和临时链接"]
    Remove --> Source{"目录导入？"}
    Duplicate --> Source
    Source -->|否| Done["记录结果；继续批次"]
    Source -->|是| Remain{"源目录中还有受支持媒体或 SRT？"}
    Remain -->|是| Retain["保留目录和剩余文件"]
    Remain -->|否| Linked{"还有符号链接子目录？"}
    Linked -->|是| Retain
    Linked -->|否| Delete["删除源目录及剩余的非媒体内容"]
    Retain --> Done
    Delete --> Done
```

移动文件采用同一文件系统内的硬链接和 `unlink` 操作。**不会复制媒体字节，也不会回读内容进行验证。** 在媒体目录事务提交之前保留源文件。inode 比较基于文件系统元数据，而不是内容校验和。如果目的目录位于另一文件系统，操作会失败，不会悄悄复制。

SRT 随对应视频一起移动，并使用相同的主文件名。双文件电影使用 `Title (Year) Part 1.ext` 和 `Title (Year) Part 2.ext`，字幕使用对应的 `.srt` 文件名。参见[文件命名](/zh-CN/pages/file-naming/)。

目录清理会递归检查所有层级。源目录中只要还有任意大小的受支持视频、尚未解决的 SRT 或符号链接子目录，就不能删除该目录。否则可以删除整个目录，包括剩余的发行说明等非媒体文件。对于包含多部独立电影的目录，每导入一部便检查一次，尚未导入的电影会使目录继续保留。

流程图展示正常路径和目标冲突。文件系统或数据库错误会在提交/移除边界前保留源数据，并记录供检查的错误。按格式优先级删除副本和目标路径完全冲突是不同操作：后者必须明确使用 **Replace Local Media**。

参见[媒体目录数据库结构](/zh-CN/pages/schema/)以及[Control 和 Event Log](/zh-CN/pages/control-server/)。
