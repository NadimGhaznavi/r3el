---
title: "控制台、媒体目录与事件日志"
author_profile: true
layout: single
lang: zh-CN
locale: zh-CN
language_name: 简体中文
translation_key: r3el-control-server
permalink: /zh-CN/pages/control-server/
---

[返回文档目录](/zh-CN/)

# R3el 控制台

当处理停止且没有匹配结果，或者多个匹配仍未解决时，对应行的 **Action** 列会出现文本框和 **TMDB ID** 按钮。输入一个正整数电影 ID，即可获取该 TMDB 记录，即使它不在原来的候选结果中。操作在后台运行，沿用正常的媒体目录、图片、移动与格式优先级流程。查询失败会显示错误，并保留原始匹配结果以供更正。正在处理、已解决、Ignore 和 Delete 的行没有手工匹配操作。

网站默认打开 **Catalogue**，导航顺序为 Catalogue、Control、Event log。控制台位于 `/control`。

**Catalogue** 菜单链接在标志旁展示最近添加的四个条目。箭头按钮以每组四个浏览更早或更新的内容。按标题搜索会匹配标题子串，并在单独的 Search Results 面板中以每行五张的形式展示海报/标题/年份卡片。单击卡片打开电影详情，包括海报、简介以及 Director、Producers、Cast 和 Files 区块。这些页面只读取已保存的媒体目录和本地图片，不重新查询 TMDB。

电影及单集页面具有 **Watch** 按钮。每次点击会打开 VLC，并单独记录一条观看事件，包括重复观看。最近观看日期以 **Watched: YYYY-MM-DD** 显示在日期和片长下方，使用已保存的 UTC 日期。未观看条目显示 **Watched: Never**。单集页面将图片和标题放在同一行，其余信息列在下方。

`watched` 表保存唯一事件 ID、电影或单集 ID，以及点击时的 UTC 时间。安装或升级服务会创建该表。

Watch 根据保存的视频路径，将开头的 `/exports/` 替换为 `/imports/`，例如 `r3el-vlc:///imports/disk1/Movie.mkv`。其他路径前缀保持不变。页面不显示路径；同一电影有多个视频时会提供部分/版本选择器。字幕文件不能作为播放目标。

在运行 Chrome 和 VLC 的 Linux 桌面，以普通用户身份（不要 sudo）从 R3el 代码目录执行一次：

```sh
python3 scripts/vlc-link.py --install
```

也可以只复制 `scripts/vlc-link.py` 到该桌面，以 `--install` 运行。需要 Python 3、在 PATH 中的 VLC（`vlc`）、xdg-utils 的 `xdg-mime` 和 desktop-file-utils 的 `update-desktop-database`。安装器刷新桌面程序缓存，并通过 [desktop entry](https://specifications.freedesktop.org/desktop-entry/latest-single/) 为当前用户注册 `r3el-vlc:` 协议处理器。单击 Watch，确认 Chrome 的外部应用提示。视频必须在这台桌面的 `/imports/...` 中挂载。这是用 VLC 打开**本地文件**，而不是从 R3el 服务器流式传输。

Title Search、Search Index、Category Search 和 Random Search 排在同一行。Random Search 只有一个 Search 按钮，可将最近添加的列表替换为随机四部电影、电视剧或单集（总数少于四时展示全部）。每次点击重新随机选择，同一次结果中没有重复。单集卡片使用系列海报，链接到系列页面中对应的剧集。索引把 Numbers and Symbols 放在单独一行，字母在下面较窄的行中换行，按电影或电视剧标题首字符索引（不是单集标题）；忽略前导空格。索引结果和其他搜索使用相同的卡片及结果数量。没有匹配标题的字母不会显示，每个字母左右各有两个额外空格。Title Search 的 Type 独占一行。中间框按内容调整，Category Search 占据 Random Search 之前的剩余宽度；窄屏幕下各区块竖向排列。

`r3el-control.service` 是独立的 Jinja2 报表服务器。无论识别服务运行还是停止，它都能展示 MariaDB 事件日志，且不需要 Qwen。Control 页在带边框的面板内将标志与垂直对齐的设置并排放置。工作区为空时，提供 Source 文本框（预填 `DR3el.FILM_DIR`）、Destination 文本框（预填 `DR3el.MEDIA_DIR`）、Batch Size 自由数字输入（正整数，默认 10）以及 New Batch 按钮。最大值为 4,294,967,295，与数据库列容量一致。按钮通过 ZeroMQ 将目录和大小发送给识别服务器。标签与结果消息使用 Jinja2；共享默认值定义在 `DR3el`，消息名在 `DMessage`。R3el 标志随服务器资源一起部署。New Batch 会立即进行识别和 TMDB 匹配，没有中间等待步骤。

控制服务器是一套由人操作的网页程序。**打开网页或刷新状态绝不会自行启动批次**。识别服务重启时，使用保存的批次参数和文件检查点恢复中断的工作。已完成批次及明确 Stop Batch 的批次保持空闲。只有提交 New Batch 才会创建新选择。空工作区或完成的批次可使用该操作；活跃批次时禁用。New Batch 会用新选择替换完成的工作区，但保留媒体目录、文件和事件历史。工作进程完成后不会自动清空工作区或开始下一批。

工作区中有批次时，主页按选择顺序展示文件名和保存的状态。前两列为 `#`（从 1 开始）和 `Updated`（浏览器本地时间的 `MM-DD HH:MM`）。Updated 表示文件最后一次保存更改的时间，而不是最近页面刷新。旧工作区记录显示 `—`，直到有实际更改；升级不会虚构历史时间。处理期间 Control 区域变灰，保存的目录和批次大小变为静态文本，New Batch 被禁用。完成、失败或停止后，先前设置又可编辑，空批次也一样。进度轮询会在完成时重新启用 New Batch。工作区替换与新选择在同一事务中提交；选择失败或数据库事务失败不会破坏原工作区。

文件表末尾为 **Action** 列，适用时显示 **TMDB ID** 或 **Replace Local Media**。不再提供 Pending / Approve / Ignore / Delete 下拉框。有工作区时可使用 **Clear Current Batch**：该操作会先安全停止处理，再清除工作记录，同时保留媒体目录、已导入文件与事件。控件下方黄色粗体 **Current Task:** 行显示当前批次最新 Event Log 消息，可进入详情。

批次内的文件每组最多处理 10 个。每组完成识别、TMDB 匹配、LLM 候选选择和零结果重试后，才开始下一组；未轮到的文件保持 Pending，最后一组可以少于 10 个。

**Stop Batch** 请求以协作方式停止自动处理或手工 TMDB ID 匹配任务。停止请求独立于工作进程的独占锁进行提交。当前操作会安全完成，之后在新文件或新识别重试前停下。正在进行的模型/API 调用必须返回或超时；按钮不会杀死服务，也不会中断数据库事务或文件移动。已完成的工作照常保留，尚未触碰的 Pending 不变，批次标记为 `cancelled`，界面显示正在停止/已停止。停止请求可跨重启保留，后续匹配请求不能悄悄恢复。这不会清除工作区，也不会新增 Resume 操作。

每组识别后，服务器根据保存的片名和年份自动对 Pending、Approve 文件执行 TMDB 电影搜索。Ignore、Delete 跳过且不进行文件操作。New Batch 与 Stop Batch 一起位于 Refresh 下方。没有 Process Batch 按钮；可用 TMDB ID 修正未解决的匹配。后台工作进程锁定工作区，此时动作更改会发生冲突。同一活跃批次的重复提交返回同一任务，不会新建额外工作。每个文件搜索结束后立即保存结果。

匹配完成后，Match Results 链接根据 TMDB 总数显示 **1 match**、**No matches** 或 **N matches**。**Match failed** 链接指向错误，**Skipped** 不提供链接。详情页展示查询的标题/年份及每个下载候选的卡片：海报、标题/年份、语言、评分/票数、类型、简介、上映日期、原名和 TMDB 链接。只有一个总结果时视为 Resolved；多个结果启动 `multiple_choice` LLM 提示，提供候选编号、片名及约 160 字符且延伸到句末的简介片段。模型经 MCP 调用 `submit_multiple_choice(number)`。临时回环 ZeroMQ 监听器对照服务器持有的尝试和候选数验证整数，拒绝过期或重复的提交。工具参数**只有编号**。有效选择被保存为 Resolved；0 表示无法自信选择。成功后，**1 match** 链接和保存的 JSON 仅包含被选中的电影，其他候选从工作区结果中清除。纯文本数字不能算作工具提交。

无效的模型回复与连接故障让结果保持 Ambiguous，可重新选择而无需再次搜索 TMDB。选择仅使用已下载的第一页。Control 从 `/etc/r3el/server.env` 读取 `R3EL_LLM_URL`，默认使用本地 Qwen。缺少元数据时显示明确的占位值；小屏幕采用上下堆叠布局。保存的 JSON 可在折叠的详情块中查看。如果实际结果超过已下载的第一页，页面会注明显示数量。打开或刷新详情只读保存的结果，不再查询 TMDB。再次匹配会复用成功的查询，并重试失败的查询。更改文件动作会清除该文件结果。没有识别结果的 Pending/Approve 显示 Match failed。识别缺失或单项查询失败不会阻止其他文件继续处理。

TMDB 零结果会自动开启新的文件名识别对话，使用正常的当前日期、focus、文件名和提交提示。过去的识别与搜索失败不会放入新 LLM 消息。新片名与年份会再次搜索，即使与先前完全相同。**Retries** 列最多记录初次识别后的三次额外识别。如果第三次仍没有匹配，则按最终片名依次搜索前一年和后一年。相邻年份搜索第一次返回**恰好一部电影**时直接接受；多个结果走正常 LLM 选择，无法选择则留给手工 TMDB ID。只有零结果才继续搜索下一个年份。若前后年份均无结果，使用手工 TMDB ID 字段。文件进入 `unresolved_llm`，之后的匹配请求不会再执行已耗尽的重试；批次继续其他文件。API 故障不算作零结果；失败的相邻年份可单独重试，无需重新搜索已完成的年份。进行识别重试、相邻年份搜索或 LLM 多候选选择时，Status 列显示 Pending。重试次数和结果与事件一起保存，可跨重启恢复；安装/升级新增 `media_files.retries`。同一次识别对话内部的表单纠错次数是另一个计数器。

`POST /workspace/match` 接收 `batch_id`，迅速返回 HTTP 202、`accepted: true` 和 `job_id`。`GET /workspace/match/status/<job_id>` 报告 `running`、`completed` 或 `failed`。浏览器每两秒轮询任务状态和保存的文件进度，完成后就地更新表格。处理过程中重新加载页面会恢复轮询，而不是再次提交任务。错误会停止轮询，并提示查看保存的结果。工作进程拥有独立数据库连接，不依赖浏览器；服务关闭会等待其完成。最近任务状态存在内存中；服务重启后旧任务 ID 返回 404，但保存的文件结果仍在，处理可重试。`GET /matches/<batch_id>/<file_id>` 展示保存的匹配。更改动作不会立即操作文件。`POST /workspace/actions` 接受 `batch_id`、`file_id` 和 `action`，以 JSON 返回保存后的就绪状态。

New Batch 被接受两秒后，Control 页面只重新加载一次，以展示发现的文件，并返回 `/control`，移除接受标记，防止刷新时重复提交。自动处理期间表格每两秒更新，直到完成或失败。Refresh 下拉框提供 Manual（默认）、5 秒、30 秒、1 分钟，并配有 Update 按钮。刷新仅更新文件表、按钮可用状态和最后更新时间，页面及表单输入保持不变。Update 不导航即可应用间隔。动作菜单获得焦点或正在保存时暂缓刷新。选择的间隔保存在 URL 中，New Batch 被接受及匹配完成后仍有效。Current Batch 面板将文件表放在独立的边框框内，长批次在框内滚动，列标题固定。面板标题右侧 **Updated** 使用浏览器本地时间 `MM-DD HH:MM:SS`，表示**页面最近读取工作区的时间**，不是文件最后修改时间。Pending 文件直到保存结果才改变状态。读取工作区时不占用处理进程的独占锁。数据库故障时显示 Workspace unavailable，不显示按钮。

New Batch 替换完成的工作区；服务启动恢复中断的批次。批次保存的输出目录供匹配后的自动导入使用。开始任务前设置识别服务器的 `--llm-url` 或 `R3EL_LLM_URL`。`accepted` 是立即回复，只表示已接受处理，**不表示已完成**。工作期间其他命令返回 `busy`，不会排队。批次运行时监听器继续处理 MCP 提交；完成后恢复空闲。到 `/events` 查看结果；如果在创建工作区前出错，请查看服务日志。超时结果不确定，绝不自动重试。

`POST /batches` 处理表单，成功时重定向到 GET 页面，使刷新不会重交任务。两项服务都支持 `--zmq-endpoint` 非默认端点；参见 [ZMQ 消息](/zh-CN/pages/zmq-messages/)。

安装/升级会复制 Python 模块与模板、初始化事件和工作区结构，然后启用并启动控制服务。访问 `http://<server>:42220/`。默认根据 `DR3el.CMDB_NETWORK` 的 `http` 声明监听全部网络接口，并应用生产 JSON 覆盖设置（[配置](/zh-CN/pages/configuration/)）。独立批处理服务保持停止且不启用自启，直到手工启动。卸载会删除两个 R3el 服务，但保留 Qwen。

Event Log 按时间倒序展示最多 500 条匹配事件。Category、subcategory、event-name 下拉框位于表格第二层标题行，先对数据库**全部历史**过滤，再限制条数。Event / source 下拉框可筛选 `tool_received`、`tool_started` 等事件。行内首先单独展示源，例如 `FileMgr - files_retrieved`。可选择手工或 5、30、60 秒自动刷新。单击事件进入完整消息、来源、进程 ID、应用版本和父事件。详情页缩进显示 JSON，原始文本保持不变。`reply_received` 的 Message 区域将解码后的 LLM reasoning 以 Markdown 格式展示，支持标题、列表、强调、代码、表格与换行。完整日志负载仍位于 JSON 标题下。内嵌 HTML 被转义，不安全链接协议被阻止；无 reasoning 时显示专门的空状态信息。显示时间按浏览器本地时区和夏令时转换；数据库始终保存 UTC，时间戳元素包含明确的 UTC 偏移。

## TMDB 事件

每次 API 请求前，电影匹配记录 **TMDB / Search** 类别的 `tmdb_search`，包含文件名、片名、`primary_release_year`、页码与端点。`tmdb_result` 属于 **TMDB / Result** 并链接到对应搜索；详情包含完整响应或错误、查询标题/年份及结果。搜索事件链接到批次开始事件，两者都有批次和文件 ID。**凭据与授权头绝不写入日志。**

结果事件与工作区匹配结果在同一事务中提交。预期的搜索失败使用 ERROR 严重程度，零或多个结果保持 INFO。如果缺少配置或识别信息，失败事件直接链接批次，因为根本没有执行搜索。Ignore/Delete 文件及复用成功的保存结果都不生成搜索/结果事件。真正的每次重试会创建自己的事件对。仅查看保存结果不生成匹配事件。

媒体目录处理对每次海报/背景下载、复用或失败记录 **Artifact / Download**；目录元数据和文件关联提交时记录 **DB / Create Record**；源文件移除完成或失败时记录 **File / Move**。事件带有批次/文件上下文，并链接到批次事件。目录记录事件与数据库事务同步提交，移动事件与完成检查点同步保存。批次恢复不会为已完成的文件重复记录这些事件。

## 消息模板

Message 列使用 `r3el/server/templates/messages/` 下的 Jinja 模板。`EventPages` 优先选择 `<event-name>.html`，不存在时采用 `default.html`。模板选择只根据事件名称；Category/Subcategory 只影响筛选。默认模板显示带缩进的 JSON 或原文本，最多 1,200 字符，超过时以省略号结尾。**整个预览都是事件详情链接**，没有单独的 Full event 链接，包括服务器生命周期事件。

每个专用模板控制整个 Message 单元格，整体链接到 `/events/<event_id>`：

| 事件 / 模板名 | 显示内容 |
| --- | --- |
| `files_retrieved` | `Retrieved filenames (XXX): foo.txt, bar.xls, ...`：总数、保存顺序的前两个文件名及字面 `...`。 |
| `batch_started` | `Batch started with size: XXX`，使用 `data.batch_size`。 |
| `batch_completed` | `Batch completed with size: XXX, unresolved_llm: YYY`，使用 `data.count` 和 `data.unresolved_llm`。 |
| `attempt_started` | `Filename: …`，使用 `context.filename`。 |
| `reply_received` | `Filename: …, Reasoning: …`，使用已解码的 `reasoning_content`，取前 20 个字符或首次换行，之后追加字面 `...`。 |
| `tool_completed` | `Tool completed. Attempts: XX, Filename: …`，使用 `context.attempt` 和 `context.filename`。 |
| `submission_accepted` | `Submission accepted. Attempts: XX, Filename: …, Title: …, Year: XXXX, Confidence: XX.`，使用尝试上下文和 `data.identification`。 |
| `tool_received` | `Tool received. Attempts: XX, Filename: …, Title: …, Year: XXXX, Confidence: XX.`，使用提交的 `data`，缺失字段显示 `—`。 |
| `item_started` | `Filename: …`，使用 `context.filename`。 |
| `item_completed` | `Filename: …`，使用 `context.filename`。 |
| `batch_failed` | 仅 `data.error`。 |
| `tmdb_search` | 链接文件名、标题和上映年份；详情包含查询参数。 |
| `tmdb_result` | 链接文件名和匹配数量或错误；详情包含响应或错误信息。 |
| `file_move` | 链接文件名、源与目标路径，以及移动结果或错误。 |
| `file_delete` | 链接文件名、重复文件路径、优先保留的视频路径，以及删除结果或错误。 |
| `artifact_download` | 链接文件名、图片类型、源 URL、本地路径及下载/复用结果或错误。 |
| `db_create_record` | 链接文件名、片名、TMDB ID、本地视频路径及目录保存结果。 |
| `batch_cancelled` | `Batch cancelled`。 |

`batch_resumed` 等没有自定义模板的事件采用默认模板。置信度要求并接受 0–10 的整数，原样保存与显示。`tool_received` 在验证前显示提交值，缺失字段使用 `—`。

每个模板收到：

- `event`：事件元数据及原始 `content`。
- `message.payload`：解码的 JSON 或原始文本。由 `EventWriter` 创建的事件含有 `message.payload.context` 和 `message.payload.data`。
- `message.text`：完整缩进 JSON 或原始纯文本。

使用简洁 HTML 和 Jinja 表达式选取字段、标签与布局；计算逻辑留在 Python 中。HTML 转义默认启用，缺少必需变量和模板错误正常暴露。只有事件专用模板**不存在**时才使用默认模板，而不是专用模板损坏时进行静默回退。

要自定义事件，新建以事件名命名的模板，并把路径加入 `scripts/install-services.sh` 的 `modules` 列表，以便安装及升级时部署。无论 Message 列如何显示，完整事件页始终保留全部负载；`reply_received` 还会在其上方格式化显示 reasoning。

## 独立启动

从代码目录或安装目录执行 `scripts/services.sh start` / `scripts/services.sh stop`，可启动或停止已安装的 R3el 服务。脚本按需使用 sudo。启动顺序为 Control、R3el 批处理服务器；停止顺序相反。Qwen 单独管理，此脚本不会启动或停止它。命令失败会使脚本停止并返回错误。服务器以空闲 MCP/ZeroMQ 监听状态启动；参见[识别服务器](/zh-CN/pages/one-batch-identification/)。

在安装依赖、初始化事件数据库结构，并设置环境变量 `DB_HOST`、`DB_USER`、`DB_PASSWORD`、`DB_NAME` 后：

```bash
.venv/bin/python -B -m r3el.server.ControlServer --host 127.0.0.1 --port 42220
```

`GET /` 读取 MariaDB，展示批次控件或保留的工作区；`/events` 展示日志，`/events/<id>` 展示单个事件。`/health` 仅检查 HTTP 服务器存活，不访问 MariaDB；报表页数据库故障返回 HTTP 503。无效筛选器返回 HTTP 400，事件不存在返回 HTTP 404。数据库错误详情可查看服务日志：

```bash
journalctl -u r3el-control.service -f
```

`ControlServer` 负责 HTTP 和请求级数据库连接，`EventPages` 渲染与服务器一起部署的模板。`EventReport` 处理类别筛选，`EventLogDb` 通过共享 `DbMgr` 读取数据库。

## TMDB 凭据

安装和升级从 `/root/.tmdb` 读取 `TMDB_TOKEN` 和 `TMDB_KEY`，允许不加引号或带引号的赋值，以及可选的 `export` 前缀。文件作为**数据解析，绝不执行**。两项凭据都必需，并原子性写入 `/etc/r3el/tmdb.env`，与 `database.env` 一起由 root 拥有，权限 0600。Control 与批处理服务都通过 systemd 加载该文件。卸载只删除安装副本，不动 `/root/.tmdb`。源凭据缺失或无效时，安装程序会在停止服务或替换模块前中止。

电影搜索以 `TMDB_TOKEN` 作为 Bearer token；`TMDB_KEY` 与之一起保留。独立启动时在环境中提供 `TMDB_TOKEN`。参阅 TMDB [电影搜索](https://developer.themoviedb.org/reference/search-movie)和[认证文档](https://developer.themoviedb.org/docs/authentication-application)。搜索使用标题与 `primary_release_year`；恰好一个总结果视为匹配，多个结果进入 LLM 候选选择。这一步不包括电视剧搜索。

## 共享 TMDB 参考表

`tmdb_movie_genres` 保存 TMDB 类型 ID 及英文名称；`tmdb_languages` 保存 ISO 639-1 代码、英文名与本地名称。这些表属于共享应用数据，不依赖任何批次，为后续浏览界面提供支持。Match Results 通过 `TMDBReferenceDb` 读取它们。未知 ID/代码直接显示，不虚构名称。

安装及升级会显式建表、下载两份参考目录、验证并在同一事务中 upsert。下载或数据库写入失败不会破坏原有记录。刷新时保留 TMDB 当前不再返回的 ID，避免破坏已有媒体引用。不存在后台刷新或打开页面时调用 API 的行为。在数据库凭据及 `TMDB_TOKEN` 可用时，可手工执行 `.venv/bin/python -m r3el.activity.TMDBReferenceRefresh`。

数据来自 TMDB [电影类型](https://developer.themoviedb.org/reference/genre-movie-list)与[语言](https://developer.themoviedb.org/reference/configuration-languages)接口。海报使用保存的路径和 TMDB 公开的[图片 URL 格式](https://developer.themoviedb.org/docs/image-basics)；浏览器读取公开图片，不接触 API 凭据。

## 命令行 TMDB 搜索

按标题搜索，可选四位年份：

```bash
.venv/bin/python scripts/query-tmdb.py "Superman"
.venv/bin/python scripts/query-tmdb.py "Superman" 2025
```

电视剧使用 `--type tv`，默认电影类型为 `--type movie`。对于电视剧，年份筛选**首播日期**，不是每集播出年份。

```bash
.venv/bin/python scripts/query-tmdb.py --type tv "Breaking Bad"
.venv/bin/python scripts/query-tmdb.py --type tv "Breaking Bad" 2008 --raw
```

电视剧的原始结果包括系列详情及相关演职员、关键词、外部 ID、别名、分级、翻译、图片及视频，但不会逐季或逐集下载详情。

要安装具有独立虚拟环境的 CLI：

```bash
sudo scripts/install-cli.sh
/opt/prod/r3el/bin/query-tmdb "Superman" 2025
```

使用 `-r` / `--raw` 会为第一页每个搜索命中获取完整电影记录，并输出缩进 JSON。每条结果保留搜索字段，并加入 TMDB 电影详情的片长、预算、票房、类型、制作公司、系列信息，以及 `append_to_response` 提供的演职员、关键词、外部 ID、别名、上映日期、翻译、图片和视频。保留分页元数据，但不会抓取评论、推荐或后续搜索页：

```bash
/opt/prod/r3el/bin/query-tmdb -r "Superman" 2025
```

安装器创建或复用 `/opt/prod/r3el/.venv`，只安装 CLI 所需的 Python 依赖和模块。它不创建数据库，不安装或启动服务。安装后的命令可从任意目录执行，无需激活 venv，也无须保留开发检出目录。CLI 依次读取当前 shell 的 `TMDB_TOKEN`、`/etc/r3el/tmdb.env`、`~/.tmdb`（root 为 `/root/.tmdb`）。凭据文件作为数据读取，不执行；不可读的文件跳过，权限保持不变。

该脚本使用与批次处理相同的 `primary_release_year` 搜索，并展示编号结果、上映日期、语言、评分、TMDB 链接及自动换行的完整简介。第一页结果不完整和完全无匹配都会明确标示。TMDB/配置故障时退出码为 1，参数无效时为 2。它**不会**调用 LLM 或修改工作区。安装/升级会与服务管理脚本一起部署该命令。