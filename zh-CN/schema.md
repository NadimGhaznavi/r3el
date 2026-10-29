---
title: "媒体目录数据库结构"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-schema
permalink: /zh-CN/pages/schema/
---

[返回文档目录](/zh-CN/)

每个 TMDB ID 对应一个电影记录，正式媒体目录与临时批次工作区分开存储。单个搜索结果或成功的多候选选择将触发完整 TMDB 详情获取和保存。含糊不清、跳过或失败的匹配不会创建媒体目录记录。

| 数据表 | 内容 |
| --- | --- |
| `movies` | TMDB ID（主键）、片名和原名、上映日期及派生年份、简介、片长（分钟）、海报/背景路径、IMDb ID、评分、票数、UTC 元数据获取时间和首次添加时间。 |
| `people` | TMDB 人物 ID（主键）及姓名。 |
| `credit_roles` | Actor、Director、Producer、Executive Producer、Co-Producer。 |
| `movie_credits` | 电影、人物、角色类型、角色名称及演员表顺序。 |
| `tmdb_movie_genres` | 共享的 TMDB 类型 ID 和名称。 |
| `movie_genres` | 唯一的电影/类型组合。 |
| `movie_files` | 关联到电影的本地文件路径。 |
| `movie_artwork` | 关联到电影的本地海报/背景图路径及媒体类型。 |

媒体目录没有语言字段。缺失的可选元数据使用 SQL `NULL`。`release_year` 由 `release_date` 自动计算，二者不会不一致。评分和票数反映 `fetched_at` 时 TMDB 的值。

`added_at` 记录首次插入时间，用于排列最近添加的项目；刷新元数据时保留该值。已有行最初根据 `fetched_at` 初始化。

人物在电影和角色类型之间共享。同一人可以同时是某部电影的演员、导演及制片人；其扮演的不同角色保留为独立演职员记录。条目位置区分同一电影中的记录，`billing_order` 保留 TMDB 演员顺序。保存前折叠完全相同的重复记录。

文件路径采用 SHA-256 键，支持长且大小写敏感的路径，无需截断唯一索引。重新处理同一路径会更新电影关联，不同路径可以关联同一电影。文件关联不依赖工作区行，清理工作区后仍存在。`movie_files.path` 是最终视频路径；`movies.poster_path` 和 `movies.backdrop_path` 保留 TMDB 远程路径；`movie_artwork.path` 保存已下载的本地图片路径。

目的目录来自批次定义，不额外添加固定根目录或 `movies` 部分。电影目录名为 `Title (Year)`，视频为 `Title (Year).ext`，详见[命名规则](/zh-CN/pages/file-naming/)。片名及年份取自 TMDB；缺失上映日期时必须提示处理，而不是虚构年份。图片名可为 `poster-<TMDB-image-name>.jpg` 或 `backdrop-<TMDB-image-name>.jpg`。

源与目的目录必须处于**同一文件系统**。移动准备阶段创建硬链接，不复制或哈希媒体字节。数据库事务提交后才移除源文件名；同一事务也更新工作区中的目标路径。另一个完成检查点允许在提交或源文件移除后重试，而无须重新下载元数据。隐藏的 `.r3el-<file-id>.video` 链接标识未完成的准备，移动后会移除；`.tmdb-id` 标识目录所属电影。无关目标文件或电影身份冲突会引发可见错误，绝不覆盖。下载或数据库写入失败会保留源文件；已准备的硬链接和图片可能留待重试。

服务账户必须对源文件及两个父目录有读写权限。Control 服务使用 `ProtectSystem=full`，允许批次所选数据目录写入，同时保持系统目录只读。

保存事务会刷新电影、人物、类型、演职员和文件关联，并一起更新工作区检查点及事件。事务失败则回滚所有更改。电影元数据刷新替换其类型和演职员关联，但保留其他文件关联。

完成的工作区匹配带有媒体目录检查点，重复处理时不会重新下载元数据。已匹配却缺少检查点的旧记录在再次处理时会保存。元数据错误不丢弃所选匹配，会显示错误并允许不重新搜索直接重试。

`scripts/install-services.sh` 在安装和升级时运行 `r3el.activity.CatalogueSchema`。建表具有幂等性，必须显式执行，不会在打开数据库连接时自动发生。升级保留现有数据，不自动回填历史记录。

## 电视剧层级

电视剧使用 `tv_series`、`tv_seasons`、`tv_episodes` 和 `tv_episode_files`，另有 `tv_artwork`、`tv_series_genres`、`tmdb_tv_genres`、`tv_series_credits` 与 `tv_episode_credits`。人物表 `people` 和 `credit_roles` 与电影共享。

一个系列内季号唯一，一季内集号唯一；第 0 季表示特别篇。剧集文件路径使用与电影相同的 SHA-256 键。目录和附件导入检查点会在源文件名移除前一起提交。参见[电视剧导入](/zh-CN/pages/tv-shows/)。

工作区条目保存 `media_type`；附件保存 `season_number`、`episode_number` 和 `import_result`。批次保存 `tv_destination_directory`，即与电影目的目录同级的 `tv` 目录。已保存的电视剧匹配包含 `episodes_mapped` 标志，只有在单独的映射对话完成并提交集号分配后才设置；仅识别剧名不设置此标志。
