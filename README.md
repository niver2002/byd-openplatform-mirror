# 比亚迪生态开放平台 · 资料镜像（2026 智能座舱设计大赛）

把 [openplatform.byd.com](https://openplatform.byd.com/) 上的**赛事资料**、**赛事资料包**与**完整开放 API 文档**
全量抓取下来，镜像成本仓库里可离线浏览、可全文检索的静态站点。

> 正文、图片、视频、附件**全部存在仓库本体里**，不是外链。
> 原站的图片和附件地址带有时效签名（`auth_key`），过几小时就会 403，本仓库里的副本不会。

**在线浏览：<https://niver2002.github.io/byd-openplatform-mirror/>**

---

## 里面有什么

| 板块 | 内容 | 规模 |
| --- | --- | --- |
| [赛事专区](https://niver2002.github.io/byd-openplatform-mirror/contest/) | 2026 比亚迪智能座舱设计大赛：赛事公告、三条赛道的定位/方向/作品要求/提交规范、奖项与权益、评委阵容、常见问题 Q1–Q10、整屏渲染快照；以及参赛规则、获奖通知说明、大赛权益说明、大赛用户协议、隐私政策、监护人知情同意书、儿童隐私保护声明 | 3 赛道 / 8 篇官方文档 / 9 个页面快照 |
| [官方赛事资料包](https://niver2002.github.io/byd-openplatform-mirror/contest/pack/) | 官方 `2026比亚迪智能座舱设计大赛资料.zip` 解包：内外饰车体图（座舱空间示意 + 整车 4 视图）、大赛设计说明、LOGO 四联标、汉仪旗黑 3 款字体、`主题&壁纸赛道大赛模版.pix`；含缩略图预览与整包原件下载 | 16 个文件 / 269 MB |
| [API 库](https://niver2002.github.io/byd-openplatform-mirror/api/) | 车机端 Java 开放 API 全量接口定义：车身状态、行驶数据、车速、能量与模式、全景摄像头、空调、空气质量、发动机、变速箱与制动、门锁、车灯、安全带、雷达、充电、轮胎、仪表、时间、传感器、媒体中心、车辆设置 | 26 篇 / 21 个接口分类 |
| [开发者文档](https://niver2002.github.io/byd-openplatform-mirror/dev/) | 知识地图、开发者注册认证、开发套件（AIoT 直连/云云对接/云设备/应用分发/主题套件）、AIoT 业务、应用分发业务、主题商店业务、平台协议、营销渠道与规则中心、活动与动态 | 99 篇 |
| [协议规范](https://niver2002.github.io/byd-openplatform-mirror/protocol/) | 软件开发协议（直连接入、云接入、OTA 升级）与硬件接口规范（螺纹、椅背、中控生态接口） | 19 篇 |
| [资料包下载](https://niver2002.github.io/byd-openplatform-mirror/downloads/) | 主题商店设计模板 `.sketch` / `.pix`、主题审核资料提供明细 `.xlsx`、车身开放 API `bydauto-openapi.jar`、接口清单 `PDF`/`xlsx`、设备使用手册、手指素材、竞品分析报告、应用软件许可授权书、准入标准审核表、应用测试报告模板等**全部可下载附件** | 16 个文件 |
| [Markdown 镜像](https://niver2002.github.io/byd-openplatform-mirror/markdown/) | 全部文档的 Markdown 版本，适合本地笔记 / 知识库 / RAG 语料 | 144 篇 |
| [全文搜索](https://niver2002.github.io/byd-openplatform-mirror/search.html) | 在全部镜像正文中检索 | — |

**单文件版本**：
[API 全量合集（一页打完）](https://niver2002.github.io/byd-openplatform-mirror/api/all.html) ·
[API Markdown 合集](https://niver2002.github.io/byd-openplatform-mirror/markdown/byd-api-reference.md)

镜像总量：**约 590 MB**：144 篇文档 + 147 份原始 JSON + 355 个正文图片/附件（305 MB） + 官方赛事资料包解包 269 MB（`docs/contest/pack/`）。

## 目录结构

```
docs/                       ← GitHub Pages 发布目录（生成物，勿手改）
├── index.html              首页
├── contest/                赛事专区
│   ├── index.html          赛事主页（公告 / 赛道 / 规则 / 资料清单 / 页面快照）
│   ├── captured/           无头浏览器渲染的官方页面：DOM、纯文本、整屏截图
│   ├── pack/               官方赛事资料包解包（PNG / TTF / PIX / DOCX + 缩略图 + manifest）
│   └── data/               赛事接口原始响应 + 赛道数据 JSON
├── api/                    API 库（含 all.html 全量单页合集）
├── dev/                    开发者文档（99 篇）
├── protocol/               协议规范（19 篇）
├── downloads/              资料包附件（PDF / DOCX / XLSX / ZIP / JAR / SKETCH / PIX）
├── assets/                 正文内嵌图片与视频（文件名带哈希后缀）
├── markdown/               全部文档的 Markdown 镜像
├── raw/                    每篇文档的原始 JSON 响应（含富文本 HTML）
├── manifest.json           每个资源的原始 URL ↔ 本地路径 ↔ 体积
├── omitted.json            因体积上限未收录的文件
└── search.json             全文检索索引
scripts/                    采集与构建脚本（纯 Python 标准库，无需第三方依赖）
```

## 怎么更新

**注意：GitHub 自己的托管 runner 抓不了这个站。** 实测 runner 能解析 DNS，但到
`openplatform.byd.com`（华为云 CDN，124.71.75.52）的 TCP 连接永远建不起来，90 秒超时；
`openplatform-cdn.byd.com` 同理。所以抓取必须在一台**能访问国内网络**的机器上做，
抓完再推到 GitHub。

仓库自带一键脚本：

```powershell
# 1) 抓取 + 渲染快照 + 构建站点（约 5 分钟，600 MB）
pwsh -File scripts/refresh.ps1

# 2) 提交并分批推送（默认 60 MB 一批，失败自动重试）
git add -A
git commit -m "chore(mirror): refresh"
python scripts/push_batched.py --batch-mb 60
```

`refresh.ps1` 的参数：`-MaxVideoMb`（单个视频上限）、`-BudgetMb`（媒体总量预算）、
`-SkipMedia`（只抓文字）、`-SkipCapture`（跳过浏览器快照）。

推完 GitHub Pages 会自动重新发布 `main` 分支的 `/docs` 目录。

### 分批推送为什么必要

整包约 600 MB，单次 `git push` 在跨境链路上很容易被 reset。`push_batched.py` 会把改动切成
若干 60 MB 的 commit 依次推送，每批成功即落盘，中途失败不会丢失已完成的部分。

## 采集自哪些接口

| 接口 | 用途 |
| --- | --- |
| `POST /api/document-portal/document/portal/getUpDocument` | 文档树（`documentType=1` 开发者文档、`2` 协议规范、`3` API 库） |
| `GET /api/document-portal/document/portal/getUpDocumentContent?id=` | 单篇文档富文本 HTML |
| `GET /api/message-portal/announcement/list` | 赛事公告 |
| `GET /api/document-portal/activity/listOnline` | 首页活动位 |
| `GET /api/document-portal/document/portal/getAdvertisementByPosition` | 首页广告位 |
| `GET /api/theme-portal/contest/getContestSchedule?contestEdition=2` | 赛程（需登录态，返回「登录令牌丢失」，未收录） |
| `GET /api/theme-portal/contest/*` | 报名 / 上传作品 / 我的作品（均需登录，未收录） |

赛事页的数据不是接口给的，而是打包在前端 JS 模块 `assets/data-wZb2jLnm.js` 里（赛道与资源清单），
页面文案则在页面 chunk 中，所以额外用无头浏览器把 `#/theme-competation/*` 渲染后存档，
见 `docs/contest/captured/`。

### 关于「赛事资料包」

赛事资源页（`#/theme-competation/resources`）的 5 个条目在中前台数据里 `downloadUrl` 为空，点击提示
「资源即将上线，敬请期待」。**但官方真正的资料包是另一个静态文件**：

```
https://openplatform.byd.com/2026比亚迪智能座舱设计大赛资料.zip   (253 MB, 2026-11-17)
```

这个包已经完整镜像，两种取用方式：

- **在线浏览 / 单文件下载** → <https://niver2002.github.io/byd-openplatform-mirror/contest/pack/>
  解包后 16 个文件共 269 MB：内外饰车体图（座舱空间示意 2 张 + 整车 4 视图 4 张）、
  大赛设计说明 4 张、LOGO 四联标、汉仪旗黑 3 款字体、`主题&壁纸赛道大赛模版.pix`(82.5 MB)。
  图片都生成了缩略图，可直接预览。
- **整包原件下载** → [Release 附件](https://github.com/niver2002/byd-openplatform-mirror/releases/download/contest-pack-2026/byd-2026-cockpit-design-contest-pack.zip)
  （253 MB，253,566,688 字节，SHA-256 `f62c0547c8d534e92ff6a3604b9340b32047106e66ad9e89a76becd4b4de890`）

压缩包本体超过 git 单文件 100 MB 上限，所以放在 Release 附件里；包内每个文件都单独入库，
单文件最大 82.5 MB，无需 LFS。此外仓库还镜像了文档中其余 16 个可下载附件（主题商店设计模板
`.sketch`/`.pix`、审核资料明细、车身开放 API JAR、接口清单、准入审核表等），见
[下载页](https://niver2002.github.io/byd-openplatform-mirror/downloads/)。

> 官方后续若更新资源包，重跑 `scripts/refresh.ps1` 会重新下载解包；`pack.py` 里的 `PACK_URL` 是固定地址。

## 版权与免责声明

本站内容版权归**比亚迪汽车工业有限公司**所有，仅为参赛者与开发者**离线查阅、检索**之便利做技术性归档，
未改写任何文字内容，未用于商业用途。

- 原始站点：<https://openplatform.byd.com/>
- 若权利人认为本镜像不妥，请提交 issue，将立即删除。
- 请勿将本仓库内容用于商业转载。

## 许可

`scripts/` 下的采集与构建脚本以 MIT 许可提供；
`docs/` 下的抓取内容版权归原权利人，**不在** MIT 许可范围内。
