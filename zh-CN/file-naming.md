---
title: "文件命名"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-file-naming
permalink: /zh-CN/pages/file-naming/
---

[返回文档目录](/zh-CN/)

批次的输出目录就是目标根目录。每部成功识别的电影按照下述规则创建 `Title (Year)` 文件夹，视频使用同样的名称和原有扩展名。例如，当批次输出为 `/exports/disk1/archive/media/movies` 时：

```text
/exports/disk1/archive/media/movies/Title (2020)/Title (2020).mkv
```

海报与背景图下载到电影目录中，由媒体目录引用。电影的名称和年份取自已确认的 TMDB 条目。

默认输出目录为 `/exports/disk1/archive/media/movies`。双文件电影使用 `Title (Year) Part 1.ext` 和 `Title (Year) Part 2.ext`；关联的 SRT 字幕使用对应视频的主文件名，如 `Title (Year) Part 1.srt`。文件在同一文件系统内移动，不复制其内容；参见[导入及清理](/zh-CN/pages/import-cleanup/)。

多个媒体格式匹配同一部 TMDB 电影时，按以下优先顺序保留首个可用格式：`mkv`、`mp4`、`m4v`、`avi`、`mov`、`wmv`、`flv`、`mpg`/`mpeg`。扩展名比较不区分大小写；`mpg` 与 `mpeg` 优先级相同，若已有相应目录记录，则保留原文件。这是**容器格式偏好**，并不代表对分辨率或编码质量的评估。

保存优先格式后，低优先级版本会被删除，其媒体目录文件关联也随之移除。即使更好的格式来自后续批次，该规则也适用。清理操作带有可重试的检查点，在事件日志中记录为 File / Delete。同扩展名文件依然遵循现有的路径冲突保护，不会因格式政策而被自动删除。

以下 Python 函数实现文件名规范化。代码注释保留原文，以便示例原样复制使用。

```python
import re
import unicodedata


def movie_filename(title: str, year: int, extension: str) -> str:
    title = unicodedata.normalize("NFKC", title)

    replacements = {
        ":": " - ",
        "/": " - ",
        "\\": " - ",
        "#": "",
        "%": " percent ",
        '"': "",
        "*": "",
        "?": "",
        "<": "",
        ">": "",
        "|": "",
    }

    for old, new in replacements.items():
        title = title.replace(old, new)

    # Normalize curly apostrophes/quotes.
    title = title.replace("’", "'")
    title = title.replace("‘", "'")
    title = title.replace("“", "")
    title = title.replace("”", "")

    # Collapse whitespace and tidy separators.
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*-\s*", " - ", title)
    title = title.strip(" .-")

    extension = extension.lstrip(".")

    return f"{title} ({year}).{extension}"
```
