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
├── scripts/                 # WordPress 导入、定时同步和远程资源本地化脚本
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

front matter 是文章顶部的元数据，控制标题、发布时间、链接、分类、标签、首页卡片和评论数量等。上面每个字段含义如下：

| 字段 | 类型 | 是否常用 | 作用 |
| --- | --- | --- | --- |
| `title` | 字符串 | 必填 | 文章标题。会显示在首页卡片、文章页标题、归档页、网站地图、RSS 和浏览器标题里。 |
| `date` | 时间 | 必填 | 文章发布时间。首页排序、归档年份月份、文章页日期都依赖它。建议使用带时区的格式，例如 `2024-01-05T10:00:00+08:00`。 |
| `draft` | 布尔值 | 必填 | 是否草稿。`true` 表示默认构建不会发布；`false` 表示正式发布。使用 `hugo server -D` 可以预览草稿。 |
| `slug` | 字符串 | 推荐 | 文章 URL 的短名。配合 `hugo.toml` 里的 `posts = "/archives/:slug/"` 生成最终链接。 |
| `categories` | 字符串数组 | 推荐 | 分类。首页卡片会显示第一个分类，分类页也会按这里生成。通常一篇文章放 1 个主分类即可。 |
| `tags` | 字符串数组 | 可选 | 标签。用于标签页和文章归类，可以写多个。 |
| `views` | 数字 | 可选 | 阅读量展示用。静态站不会自动增加阅读量，这里只是显示初始数字或迁移旧站阅读量。 |
| `comment_count` | 数字 | 可选 | 评论数量展示用。旧评论静态导入时可以填真实数量；新文章可以填 `0`。 |

常用可选字段：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `featured_image` | 字符串 | 文章特色图。文章页头图、上一篇/下一篇背景图会优先使用它。留空时使用 `hugo.toml` 的 `params.heroImage` 或随机图。 |
| `excerpt` | 字符串 | 首页卡片摘要。留空时 Hugo 会从正文自动生成摘要。 |
| `url` | 字符串 | 强制指定文章最终 URL。需要兼容旧链接时使用，例如 `url = "/archives/1269/"`。写了 `url` 后会覆盖 `slug` 生成规则。 |
| `aliases` | 字符串数组 | 旧链接重定向。适合文章换新 URL 后保留旧入口，例如 `aliases = ["/old-post/"]`。 |
| `author` | 字符串 | 文章作者。模板默认主要使用站点作者，通常不用每篇都写。 |
| `lastmod` | 时间 | 最后修改时间。部分主题、RSS 或 SEO 工具会用到。 |

更完整的文章示例：

```toml
+++
title = "My First Post"
date = "2024-01-05T10:00:00+08:00"
lastmod = "2024-01-06T18:30:00+08:00"
draft = false
slug = "my-first-post"
categories = ["Hugo"]
tags = ["demo", "guide"]
featured_image = "/images/hero.svg"
excerpt = "这是一篇用于演示 front matter 写法的文章。"
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

如果你写了：

```toml
url = "/archives/1001/"
```

最终文章链接会固定为：

```text
/archives/1001/
```

写正文时，front matter 结束后的内容就是文章正文：

```markdown
+++
title = "My First Post"
date = "2024-01-05T10:00:00+08:00"
draft = false
slug = "my-first-post"
+++

这里开始写正文。

## 二级标题

可以写 Markdown，也可以写 HTML。
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
scripts/sync_wordpress_api.py
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

## WordPress 定时同步

如果你还想继续在 WordPress 后台发布文章，可以用 REST API 同步脚本把新文章拉到 Hugo：

详细说明见：

```text
docs/wordpress-sync.md
```

```text
WordPress REST API -> scripts/sync_wordpress_api.py -> content/posts/ -> hugo build
```

脚本文件：

```text
scripts/sync_wordpress_api.py
```

首次测试建议先 dry run：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --dry-run
```

首次正式全量同步：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all
```

之后增量同步：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run
```

同步一篇指定文章：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --post-id 1269
```

如果 WordPress REST API 需要登录权限，可以使用 WordPress 应用程序密码：

```bash
WORDPRESS_URL="https://你的WordPress域名" \
WORDPRESS_USERNAME="你的用户名" \
WORDPRESS_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
python3 scripts/sync_wordpress_api.py --since-last-run
```

脚本会生成类似这样的文件：

```text
content/posts/wp-1269.md
```

生成的 front matter 会包含：

```toml
title = "WordPress 文章标题"
date = "2026-07-06T10:00:00+08:00"
draft = false
type = "posts"
url = "/archives/1269/"
slug = "wordpress-slug"
wp_id = 1269
author = "wordpress"
categories = ["分类名"]
tags = ["标签名"]
featured_image = "https://example.com/wp-content/uploads/image.jpg"
views = 0
comment_count = 3
excerpt = "文章摘要"
```

URL 生成模式由 `--url-mode` 控制：

| 参数 | 效果 | 适合场景 |
| --- | --- | --- |
| `--url-mode wp` | 默认值，保留 WordPress REST API 返回的原文章路径 | 希望 Hugo 链接和 WordPress 旧链接一致 |
| `--url-mode id` | 强制生成 `/archives/文章ID/` | WordPress 旧站使用数字归档链接 |
| `--url-mode slug` | 不写 `url`，交给 Hugo 的 `[permalinks]` 用 `slug` 生成 | 新站不需要兼容旧链接 |

如果文章图片仍然指向 WordPress，可以在同步后自动本地化远程资源：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets
```

如果要同步后自动构建 Hugo：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build
```

脚本会在项目根目录写入本地状态文件：

```text
.wordpress-sync-state.json
```

这个文件记录上次同步到的 WordPress 修改时间，已加入 `.gitignore`，不要提交到公开仓库。

cron 定时任务示例，每 10 分钟同步一次：

```cron
*/10 * * * * cd /path/to/hugo-akina-starter && WORDPRESS_URL="https://你的WordPress域名" /usr/bin/python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build >> wordpress-sync.log 2>&1
```

注意事项：

- 脚本目前同步 WordPress 文章，不同步页面删除动作。
- 同一个 WordPress 文章 ID 会固定写入同一个 `content/posts/wp-ID.md` 文件。
- 如果你手动改了 `wp-ID.md`，下次 WordPress 文章更新后会被同步脚本覆盖。
- `comment_count` 会通过 `/wp-json/wp/v2/comments` 查询；如果评论接口不可用，可以加 `--skip-comment-count`。
- WordPress 正文 HTML 会尽量原样保留，不强制转换成 Markdown。

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
