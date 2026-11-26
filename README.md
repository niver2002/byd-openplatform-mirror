# 比亚迪生态开放平台 · 资料镜像（2026 智能座舱设计大赛）

把 [openplatform.byd.com](https://openplatform.byd.com/) 上的**赛事资料**、**赛事资料包**与**完整开放 API 文档**
全量抓取并镜像到本仓库，做成可离线浏览、可全文检索的静态站点。

> 所有正文、图片、附件都已存进仓库本体 —— 不是外链。原站的图片/附件地址带有时效签名
> （`auth_key`），过几个小时就会 403，本仓库里的副本不会。

**在线浏览**：<https://niver2002.github.io/byd-openplatform-mirror/>

---

## 里面有什么

| 板块 | 内容 | 数量 |
| --- | --- | --- |
| [赛事专区](https://niver2002.github.io/byd-openplatform-mirror/contest/) | 2026 比亚迪智能座舱设计大赛：三个赛道的作品要求与提交规范、赛事公告、参赛规则、获奖通知说明、大赛权益说明、大赛用户协议、隐私政策、监护人知情同意书、儿童隐私保护声明、页面对照快照 | 3 赛道 / 8 篇官方文档 |
| [API 库](https://niver2002.github.io/byd-openplatform-mirror/api/) | 车机端 Java 开放 API 全量接口定义：车身状态、行驶数据、车速、能量模式、全景摄像头、空调、空气质量、发动机、变速箱制动、门锁、车灯、安全带、雷达、充电、轮胎、仪表、时间、传感器、媒体中心、车辆设置 | 26 篇 / 21 个接口分类 |
| [开发者文档](https://niver2002.github.io/byd-openplatform-mirror/dev/) | 知识地图、开发者注册认证、开发套件（AIoT 直连/云云对接/云设备/应用分发/主题套件）、AIoT 业务、应用分发业务、主题商店业务、平台协议、营销渠道与规则中心、活动与动态 | 99 篇 |
| [协议规范](https://niver2002.github.io/byd-openplatform-mirror/protocol/) | 软件开发协议（直连接入、云接入、OTA 升级）与硬件接口规范（螺纹、椅背、中控生态接口） | 19 篇 |
| [资料包下载](https://niver2002.github.io/byd-openplatform-mirror/downloads/) | 主题商店设计模板 `.sketch` / `.pix`、主题审核资料提供明细 `.xlsx`、车身开放 API `bydauto-openapi.jar`、接口清单 `PDF`/`xlsx`、竞品分析报告、应用软件许可授权书、准入标准审核表、测试报告模板、设备使用手册、手指素材包等全部可下载附件 | 见页面 |
| [Markdown 镜像](https://niver2002.github.io/byd-openplatform-mirror/markdown/) | 全部文档的 Markdown 版本，适合本地笔记 / 知识库 / RAG 语料 | 144 篇 |
| [全文搜索](https://niver2002.github.io/byd-openplatform-mirror/search.html) | 在全部镜像文档正文中检索 | — |

单文件版本：
[API 全量合集（一页）](https://niver2002.github.io/byd-openplatform-mirror/api/all.html) ·
[Markdown 合集](https://niver2002.github.io/byd-openplatform-mirror/markdown/byd-api-reference.md)

## 目录结构

```
docs/                     ← GitHub Pages 发布目录（生成物，勿手改）
├── index.html            首页
├── contest/              赛事专区
│   ├── index.html        赛事主页（赛道 / 公告 / 规则 / 资料清单）
│   ├── captured/         无头浏览器渲染的页面快照（HTML / 纯文本 / 截图 / XHR 日志）
│   └── data/             赛事接口原始响应与赛道数据 JSON
├── api/                  API 库（含 all.html 全量合集）
├── dev/                  开发者文档
├── protocol/             协议规范
├── downloads/            资料包附件（PDF / DOCX / XLSX / ZIP / JAR / SKETCH / PIX）
├── assets/               正文内嵌图片与视频（文件名带内容哈希）
├── markdown/             全部文档的 Markdown 镜像
├── raw/                  每篇文档的原始 JSON 响应（含富文本 HTML）
├── manifest.json         每个资源的原始 URL ↔ 本地路径 ↔ 体积
├── omitted.json          因体积上限未收录的文件清单
└── search.json           全文检索索引
scripts/                  ← 采集与构建脚本（纯标准库 + Playwright）
.github/workflows/crawl.yml ← 抓取 + 提交 + 发布
```

## 怎么更新

内容由 GitHub Actions 在 **GitHub 的机器上**抓取（不占用本地带宽），抓完自动提交回仓库并触发 Pages 发布。

- 手动触发：Actions → **Mirror BYD Open Platform** → Run workflow
- 参数：`max_asset_mb`（单文件上限）、`max_video_mb`（视频上限，默认 15MB，超过只记录原始链接）、`skip_media`（只抓文字）、`capture_pages`（是否渲染赛事页快照）
- 定时：每周一 03:17 UTC 自动刷新

本地跑（可选）：

```bash
pip install -r scripts/requirements.txt
python -m playwright install chromium
python scripts/crawl.py --out docs            # 抓文档 + API + 媒体
python scripts/render_site.py docs            # 渲染赛事页快照（可选）
python scripts/extras.py docs                 # 生成首页 / 赛事页 / 下载页 / 搜索 / API 合集
python -m http.server -d docs 8000            # 本地预览
```

## 采集自哪些接口

| 接口 | 用途 |
| --- | --- |
| `POST /api/document-portal/document/portal/getUpDocument` | 获取文档树（`documentType=1` 开发者文档、`2` 协议规范、`3` API 库） |
| `GET /api/document-portal/document/portal/getUpDocumentContent?id=` | 获取单篇文档富文本 HTML |
| `GET /api/message-portal/announcement/list` | 赛事公告 |
| `GET /api/document-portal/activity/listOnline` | 首页活动位 |
| `GET /api/document-portal/document/portal/getAdvertisementByPosition` | 首页广告位 |
| `GET /api/theme-portal/contest/getContestSchedule?contestEdition=2` | 赛程（需登录态，返回「登录令牌丢失」，未收录） |
| `GET /api/theme-portal/contest/*` | 报名 / 作品上传 / 我的作品（均需登录，未收录） |

赛事资源下载页（`#/theme-competation/resources`）的 5 个资源条目（三个赛道设计模板、品牌素材包、车机屏幕尺寸规范）
在前端数据里 `downloadUrl` 为空字符串，点击提示「资源即将上线，敬请期待」，即官方尚未放出文件本体，
因此无法镜像；仓库里镜像的是官方**实际可下载**的替代资料（主题商店设计模板、审核明细、API JAR 等）。

## 版权与免责声明

本站内容版权归**比亚迪汽车工业有限公司**所有，仅为参赛者与开发者**离线查阅、检索**之便利做技术性归档，
未对文字内容作任何改写，未用于任何商业用途。

- 原始站点：<https://openplatform.byd.com/>
- 若权利人认为本镜像不妥，请提交 issue 或联系仓库所有者，将立即删除。
- 请勿将本仓库内容用于商业转载。

## 许可

仓库内的**采集/构建脚本**（`scripts/`、`.github/`）以 MIT 许可提供；
`docs/` 下的**抓取内容**版权归原权利人，不在 MIT 许可范围内。
