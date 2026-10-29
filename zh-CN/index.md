---
title: "R3el 电影与电视剧整理工具"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-home
permalink: /zh-CN/
---

![R3el 媒体目录首页](/pages/images/main-page.zh-CN.svg)

**R3el** 使用本地运行的[大型语言模型（LLM）](https://zh.wikipedia.org/wiki/大型语言模型)，整理电影和电视剧文件。

我利用 AI 将庞大的媒体文件及文件夹收藏与 [The Movie Database（TMDB）](https://www.themoviedb.org/) 中的条目匹配，再下载海报、演员资料、剧集信息等元数据，并保存到自己的数据库。随后我开发了一个用于浏览、搜索和查看这些内容的前端界面。

这个项目的架构和代码基于我的 [Ax3l 项目](https://ax3l.osoyalce.com/)。

![R3el 架构图](/pages/images/architecture.zh-CN.svg)

## 批量处理

- [批次和单个条目的流程图](/zh-CN/pages/flowchart/)：批量处理及单个文件识别。
- [电视剧导入](/zh-CN/pages/tv-shows/)：识别剧集、映射单集并自动确定目的目录。
- [目录模式](/zh-CN/pages/directory-patterns/)：分为两部分的电影、不同年份的电影及 SRT 字幕关联。
- [导入与源文件清理](/zh-CN/pages/import-cleanup/)：文件移动、事务、冲突和清理。
- [运行时行为](/zh-CN/pages/runtime-behaviour/)：启动、停止与完成批次。

## 使用与运行 R3el

- [控制台、媒体目录与事件日志](/zh-CN/pages/control-server/)
- [识别服务器和安装](/zh-CN/pages/one-batch-identification/)
- [CMDB 声明和运行时配置](/zh-CN/pages/configuration/)
- [文件命名及格式优先级](/zh-CN/pages/file-naming/)

## 技术参考

- [持久化工作区和状态](/zh-CN/pages/file-states/)
- [媒体目录数据库结构](/zh-CN/pages/schema/)
- [ZeroMQ 消息](/zh-CN/pages/zmq-messages/)
- [编码规范](/zh-CN/pages/coding-guidelines/)

## 项目信息

- [README 中文版](/zh-CN/pages/readme/)
- [CHANGELOG（英文）](/changelog/)
- [代理开发说明中文版](/zh-CN/pages/agents/)

<footer style="margin-top: 3rem; text-align: center; font-size: 0.75em;">
  数据由 <a href="https://www.themoviedb.org/"><img src="{{ '/pages/images/tmdb.svg' | relative_url }}" alt="TMDB" width="100" style="vertical-align: middle;"></a> 提供
</footer>
