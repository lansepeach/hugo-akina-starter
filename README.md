# Akina Hugo Starter

一个可直接上传到 GitHub 的 Hugo 博客示例项目。它保留了 AkinaPro 风格的布局、移动端菜单、归档页、网站地图、友链页、静态旧评论展示和 Waline 预留能力，同时把原站个人内容替换成了示例配置与占位资源。

## 特性

- Hugo 静态博客，无数据库依赖。
- Akina 风格首页、文章卡片、文章页、页面页脚和移动端菜单。
- 首页功能卡片支持在 `hugo.toml` 自定义标题和卡片内容。
- 归档页 `/archives/` 自动根据文章生成。
- 网站地图页面 `/ditu/` 自动根据站点内容生成。
- Hugo 原生 XML sitemap `/sitemap.xml` 自动生成。
- 友链页支持纯 CSS 字母头像，也支持自定义本地或外部头像。
- 旧评论可以用 `data/comments.json` 静态展示。
- Waline 评论系统预留，配置服务地址后才加载。
- 主题 CSS、iconfont、highlight、Waline 客户端均本地化。
- 字体来源可配置。默认使用系统中文字体栈；也可以切换到小米官方 MiSans CDN 切片字体或本地 MiSans 完整字体。

## 目录结构

```text
.
├── archetypes/              # hugo new 使用的文章模板
├── assets/                  # Hugo Pipes 处理的 CSS/JS
├── content/
│   ├── page/                # 独立页面：关于、归档、地图、友链、留言板
│   └── posts/               # 文章
├── data/
│   └── comments.json        # 静态旧评论示例
├── layouts/                 # 模板
├── scripts/                 # WordPress 导入和远程资源本地化脚本
├── static/                  # 原样发布的静态资源
├── hugo.toml                # 站点配置
└── README.md
```

## 环境要求

推荐 Hugo Extended `0.131.0` 或更新版本。

检查版本：

```bash
hugo version
```

如果系统没有 Hugo，请参考 Hugo 官方安装文档：

```text
https://gohugo.io/installation/
```

## 本地运行

```bash
hugo server -D
```

默认访问：

```text
http://localhost:1313/
```

如果需要局域网或服务器外部访问：

```bash
hugo server --bind 0.0.0.0 --baseURL http://你的服务器IP:1313/
```

## 构建

```bash
hugo --minify --cleanDestinationDir
```

构建结果会输出到 `public/`。该目录已加入 `.gitignore`，通常不要提交到源码仓库。

## 上传到 GitHub

初始化仓库：

```bash
git init
git add .
git commit -m "Initial commit"
```

创建 GitHub 空仓库后，关联远程仓库并推送：

```bash
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

## 基础配置

主要配置在 `hugo.toml`。

常用字段：

```toml
baseURL = "https://example.com/"
title = "Akina Hugo Starter"

[params]
  description = "A Hugo starter inspired by AkinaPro."
  author = "Your Name"
  avatar = "/images/avatar.svg"
  logo = "/images/logo.svg"
  favicon = "/images/favicon.svg"
  heroImage = "/images/hero.svg"
  signature = "Write something about yourself here."
  notice = "Welcome to this Hugo starter."
  color = "#4c89bf"
```

上线前建议修改：

- `baseURL`
- `title`
- `params.description`
- `params.author`
- `params.avatar`
- `params.logo`
- `params.heroImage`
- `params.signature`
- `params.notice`

## 字体配置

字体在 `hugo.toml` 的 `[params.font]` 配置：

```toml
[params.font]
  provider = "system"
  preload = false
```

可选值：

- `system`：使用系统中文字体栈，不加载 WebFont，最快，适合公开 starter 默认配置。
- `misans-cdn`：使用小米官方 CDN 的 `MiSans_VF` 可变字体。官方方案会按 `unicode-range` 切片，并使用 `display=swap`，比一次加载 3 个完整本地字体快得多，但浏览器会自动请求小米 CDN。
- `misans-local`：使用本地 `static/theme/akinapro/fonts/` 下的 3 个完整 MiSans 字体文件。完全本地化，但字体文件较大。

示例，启用官方 MiSans CDN 切片字体：

```toml
[params.font]
  provider = "misans-cdn"
  preload = false
```

示例，启用本地 MiSans：

```toml
[params.font]
  provider = "misans-local"
  preload = false
```

`preload = true` 只对 `misans-local` 生效。完整 CJK 字体很大，通常不建议开启。

## 菜单配置

菜单在 `hugo.toml` 的 `[menu]` 里维护：

```toml
[menu]
  [[menu.main]]
    name = "Home"
    url = "/"
    weight = 1

  [[menu.main]]
    name = "About"
    url = "/about/"
    weight = 3
```

说明：

- `weight` 越小越靠前。
- `parent` 可以创建二级菜单。
- 站内链接建议写 `/about/` 这种路径。
- 外部跳转可以写完整 URL。

## 首页功能卡片

首页功能区标题来自 `params.featuresTitle`，卡片来自 `[[params.features]]`：

```toml
[params]
  featuresTitle = "Powered By"

[[params.features]]
  title = "Hugo Static Site"
  url = "https://gohugo.io/"
  image = "/images/features/hugo.svg"
```

图片建议放到：

```text
static/images/features/
```

然后在配置里使用：

```toml
image = "/images/features/your-image.svg"
```

这些图片会被页面自动加载。如果追求速度和稳定，推荐使用本地图片，不推荐直接使用外部图片地址。

## 写文章

新建文章：

```bash
hugo new posts/my-first-post.md
```

示例 front matter：

```toml
+++
title = "My First Post"
date = "2024-01-05T10:00:00+08:00"
draft = false
slug = "my-first-post"
categories = ["Hugo"]
tags = ["demo"]
views = 0
comment_count = 0
+++
```

文章 URL 会按 `hugo.toml` 的规则生成：

```toml
[permalinks]
  posts = "/archives/:slug/"
```

例如：

```text
content/posts/my-first-post.md -> /archives/my-first-post/
```

## 独立页面

示例项目已包含：

- `content/page/about.md` -> `/about/`
- `content/page/archives.md` -> `/archives/`
- `content/page/ditu.md` -> `/ditu/`
- `content/page/youlian.md` -> `/youlian/`
- `content/page/message.md` -> `/message/`

归档页和网站地图页不要手写列表。构建时模板会自动遍历站点文章和页面。

## 归档页

归档页入口：

```text
content/page/archives.md
```

关键配置：

```toml
layout = "archives"
url = "/archives/"
```

模板文件：

```text
layouts/page/archives.html
```

新增、删除或修改文章后，运行 `hugo`，归档页会自动更新。

## 网站地图页面

网站地图页面入口：

```text
content/page/ditu.md
```

关键配置：

```toml
layout = "ditu"
url = "/ditu/"
```

模板文件：

```text
layouts/page/ditu.html
```

Hugo 还会自动生成 XML sitemap：

```text
/sitemap.xml
```

## 友链页面

友链页说明文字在：

```text
content/page/youlian.md
```

友链列表在 `hugo.toml` 的 `[[params.friendLinks]]` 里维护。

使用纯 CSS 字母或汉字头像：

```toml
[[params.friendLinks]]
  name = "Example Friend"
  url = "https://example.com/"
  description = "A sample friend link using CSS avatar."
  title = "Example friend site"
  avatarText = "E"
```

使用头像图片：

```toml
[[params.friendLinks]]
  name = "Image Avatar"
  url = "https://example.org/"
  description = "A sample friend link using local avatar image."
  title = "Local image avatar example"
  avatar = "/images/friends/example-avatar.svg"
```

头像图片会在头像区域内自适应裁切。推荐把头像放到：

```text
static/images/friends/
```

也可以写外部头像 URL，但浏览器会自动请求外部资源，可能遇到慢请求、防盗链或隐私问题。

## 评论

### 静态旧评论

静态旧评论保存在：

```text
data/comments.json
```

示例：

```json
{
  "/archives/hello-hugo/": [
    {
      "author": "Demo Visitor",
      "date": "2024-01-04T09:30:00+08:00",
      "content": "This is a static imported comment example.",
      "avatar": "/images/avatar.svg"
    }
  ]
}
```

键名要和文章 permalink 对应。

### Waline

默认不加载 Waline。配置服务地址后才会启用：

```toml
[params]
  walineServerURL = "https://your-waline-server.example.com"
```

Waline 客户端文件在：

```text
static/vendor/waline.js
```

## 可选图片配置

默认示例项目不会显示打赏图或页脚赞助图。如果你需要，可以在 `hugo.toml` 增加：

```toml
[params]
  rewardImage = "/images/reward/wechat.jpg"
  rewardText = "微信打赏"
  footerSponsorImage = "/images/upyun-footer.png"
  footerSponsorURL = "https://www.upyun.com/"
  footerSponsorTitle = "又拍云，提供 CDN 服务"
```

对应图片应放在 `static/images/` 下，或使用你明确允许浏览器自动请求的外部图片地址。

## 静态资源

常用资源位置：

```text
static/images/avatar.svg
static/images/logo.svg
static/images/favicon.svg
static/images/hero.svg
static/images/features/
static/images/friends/
```

Hugo 会把 `static/` 下的文件原样复制到站点根路径。例如：

```text
static/images/avatar.svg -> /images/avatar.svg
```

## WordPress 迁移脚本

项目保留了迁移辅助脚本：

```text
scripts/import_wordpress.py
scripts/localize_remote_assets.py
```

如果你要从 WordPress 迁移，建议流程：

1. 从 WordPress 后台导出 WXR XML。
2. 把 XML 临时放到项目根目录。
3. 根据脚本参数或代码注释运行导入脚本。
4. 检查生成的 `content/posts/`、`content/page/` 和 `data/comments.json`。
5. 使用 `scripts/localize_remote_assets.py` 本地化会自动加载的远程资源。
6. 构建并检查页面。
7. 不要把原始 XML、SQL、压缩包等私有迁移文件提交到 GitHub。

`.gitignore` 已默认忽略 `*.xml`、`*.sql`、`*.zip` 等迁移文件。

## 部署建议

### 普通服务器

构建：

```bash
hugo --minify --cleanDestinationDir
```

把 `public/` 上传到 Web 服务器根目录。

### GitHub Pages

推荐使用 GitHub Actions 构建 Hugo，并把构建结果发布到 Pages。不同仓库的 Pages 设置不同，这里只保留源码项目，不提交 `public/`。

## 上线前检查清单

- 修改 `baseURL`。
- 修改站点标题、描述、作者、头像、Logo、首页图。
- 修改菜单链接。
- 修改首页功能卡片。
- 修改友链。
- 如需评论，配置 Waline。
- 删除不需要的示例文章。
- 运行 `hugo --minify --cleanDestinationDir` 确认无报错。
- 检查 `public/` 页面是否符合预期。

## License

本仓库是示例工程。上传公开仓库前，请根据你保留的主题资源、字体、脚本和图片来源，自行确认并补充合适的许可证说明。
