# WordPress 定时同步脚本文档

本文档说明如何使用 `scripts/sync_wordpress_api.py` 从 WordPress REST API 同步文章到 Hugo。

## 适用场景

这个脚本适合继续使用 WordPress 后台写文章，同时用 Hugo 生成静态站点的情况。

同步流程：

```text
WordPress 发布文章 -> WordPress REST API -> sync_wordpress_api.py -> content/posts/ -> Hugo 构建
```

脚本会把 WordPress 文章转换为 Hugo 内容文件。新文章默认使用：

```text
content/posts/wp-1269.md
```

如果 `content/posts/` 已有从 WXR 导入且包含相同 `wp_id` 的文件，例如 `1269-python-oop.md`，同步脚本会原位更新该文件，不会再生成重复的 `wp-1269.md`。

## 同步内容

脚本会同步这些内容：

| WordPress 内容 | Hugo front matter 字段 |
| --- | --- |
| 文章标题 | `title` |
| 发布时间 | `date` |
| 文章别名 | `slug` |
| 文章 ID | `wp_id` |
| 作者名 | `author` |
| 分类 | `categories` |
| 标签 | `tags` |
| 特色图 | `featured_image` |
| 摘要 | `excerpt` |
| 评论数量 | `comment_count` |
| 阅读量公开 meta | `views` |
| 正文 HTML | front matter 后面的正文内容 |

正文会尽量保留 WordPress 返回的 HTML，不强制转换成 Markdown，这样最不容易破坏旧文章排版。

## 前置条件

需要：

- Hugo 项目根目录里存在 `scripts/sync_wordpress_api.py`。
- WordPress 站点启用了 REST API。
- WordPress 已发布文章可以通过 `/wp-json/wp/v2/posts` 读取。
- 服务器或本地机器可以访问 WordPress 域名。

先在浏览器或终端访问：

```text
https://你的WordPress域名/wp-json/wp/v2/posts
```

如果能看到 JSON，说明公开文章接口可用。

## 是否需要用户名密码

公开已发布文章通常不需要用户名和密码。

不需要认证的命令示例：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run
```

这些情况才需要认证：

- 需要同步草稿文章。
- 需要同步私密文章。
- WordPress 安全插件限制了 REST API。
- 需要读取非公开 meta 字段。
- 站点要求登录后才能访问 `/wp-json/wp/v2/posts`。

认证使用 WordPress 的应用程序密码，不建议使用后台登录密码。

```bash
WORDPRESS_URL="https://你的WordPress域名" \
WORDPRESS_USERNAME="你的用户名" \
WORDPRESS_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
python3 scripts/sync_wordpress_api.py --since-last-run
```

## 首次测试

首次运行建议使用 `--dry-run`，只读取 WordPress 接口，不写入文件，不写入同步状态。

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --dry-run
```

如果评论接口不可用，可以先跳过评论数量查询：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --dry-run --skip-comment-count
```

正常输出类似：

```text
fetched 95 post(s)
would write content/posts/wp-1269.md
dry run: would change 95 post(s)
```

## 首次正式同步

确认 dry run 正常后，运行全量同步：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all
```

同步后会生成文章文件：

```text
content/posts/wp-37.md
content/posts/wp-52.md
content/posts/wp-1269.md
```

同时会生成本地状态文件：

```text
.wordpress-sync-state.json
```

状态文件记录上次同步到的 WordPress 修改时间。它已经加入 `.gitignore`，不要提交到公开仓库。

Linux 上脚本会使用对应状态文件的 `.lock` 文件阻止两个 cron 同步任务同时运行，避免并发写文章、状态和构建目录。

## 增量同步

首次全量同步后，日常使用增量同步：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run
```

`--since-last-run` 会读取 `.wordpress-sync-state.json`，只同步上次同步后修改过的文章。不同 `--status` 使用独立的修改时间游标。

如果不写 `--all`、`--post-id` 或 `--since-last-run`，脚本默认行为也是增量同步。

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py
```

## 同步指定文章

如果只想同步某一篇 WordPress 文章：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --post-id 1269
```

这个命令会读取：

```text
/wp-json/wp/v2/posts/1269
```

如果没有相同 `wp_id` 的已有文件，则写入：

```text
content/posts/wp-1269.md
```

指定文章同步不会推进全局增量游标，因此在首次全量同步前调试单篇文章不会跳过其他旧文章。

## 同步后构建 Hugo

同步文章后自动构建：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --build
```

默认构建命令是：

```bash
hugo --minify --cleanDestinationDir
```

如果你的构建命令不同，可以覆盖：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --build --hugo-command "hugo --gc --minify --cleanDestinationDir"
```

## 同步后本地化图片

WordPress 正文里的图片默认可能仍然指向原 WordPress 域名。

如果要同步后下载远程图片、CSS、JS、字体等资源到 Hugo 的 `static/` 目录，可以加：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets
```

本地化后的公开路径会自动包含 `hugo.toml` 中 `baseURL` 的子路径。例如 `baseURL` 以 `/hugo-akina-starter/` 结尾时，正文 HTML 会使用 `/hugo-akina-starter/uploads/...`，避免 GitHub Pages 子路径 404。运行本地化前应先把 `baseURL` 配置为实际部署地址。

同步、资源本地化、构建一起执行：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build
```

如果本次没有文章变化，默认不会执行 `--localize-assets` 和 `--build`。

如果你希望没有变化也强制执行：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build --build-always
```

如果资源本地化或 Hugo 构建失败，状态文件会保留待处理动作。下次运行会先重试这些动作，成功后才清除待处理标记。

资源下载失败时会保留原远程 URL 并返回错误，不会把 CSS、JS、字体或图片地址永久替换成错误的占位图。

同步流程调用本地化脚本时使用 `--best-effort`：失效外链仍会输出警告，但会继续构建 Hugo。若本地化真正异常或 Hugo 构建失败，待处理动作仍会保存并在下次重试。

首次增量同步且没有状态文件时，已有 `wp_id` 文件只登记源站修改时间，不会批量覆盖；源站新增而本地缺失的文章会正常创建。使用 `--all` 可强制重新比较全部文章。

## 交互式管理和 Git 推送

设置源站后运行：

```bash
export WORDPRESS_URL="https://你的WordPress域名"
python3 scripts/manage_wordpress_sync.py
```

菜单可以分两步操作：先选择同步、本地化和构建，再选择提交并推送；也可以一次完成。人工提交会预览并确认全部项目变更，cron 自动推送只暂存同步相关目录。

非交互示例：

```bash
python3 scripts/manage_wordpress_sync.py sync
python3 scripts/manage_wordpress_sync.py sync-publish
python3 scripts/manage_wordpress_sync.py publish --all-changes --yes
```

安装每 30 分钟运行一次的 cron：

```bash
python3 scripts/manage_wordpress_sync.py install-cron --minutes 30
```

自动提交并推送：

```bash
python3 scripts/manage_wordpress_sync.py install-cron --minutes 30 --auto-push --remote origin --branch main
```

日志写入 `logs/wordpress-sync.log`。Linux 上状态文件锁会阻止多个同步任务并发执行。

## 清理已下架文章

增量接口无法发现已经删除、转为草稿或不再出现在当前状态筛选中的文章。需要清理时，先 dry run：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --prune --dry-run
```

确认列表后正式执行：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --prune --build
```

`--prune` 只能和 `--all` 一起使用，只删除 `content/posts/` 中包含 `wp_id` 且未出现在完整 API 结果里的文件。它不会删除普通 Hugo 文章。

## URL 模式

脚本支持 3 种 URL 生成模式。

| 参数 | 效果 | 适合场景 |
| --- | --- | --- |
| `--url-mode wp` | 默认值，保留 WordPress REST API 返回的原文章路径 | 想让 Hugo 文章链接尽量等于 WordPress 原链接 |
| `--url-mode id` | 强制生成 `/archives/文章ID/` | 旧站使用数字归档链接 |
| `--url-mode slug` | 不写 `url` 字段，交给 Hugo `[permalinks]` 生成 | 新站不需要兼容旧链接 |

默认模式：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --url-mode wp
```

数字归档模式：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --url-mode id
```

Hugo permalink 模式：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --url-mode slug
```

项目默认 Hugo permalink 是：

```toml
[permalinks]
  posts = "/archives/:slug/"
```

如果使用 `--url-mode slug`，文章 `slug = "my-post"` 会生成：

```text
/archives/my-post/
```

## 生成文件示例

生成的文章文件大致如下：

```toml
+++
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
+++

<p>这里是 WordPress 正文 HTML。</p>
```

同一个 WordPress 文章 ID 会固定更新同一个文件。没有现有 `wp_id` 文件时，默认路径是：

```text
content/posts/wp-ID.md
```

如果已有 WXR 导入文件，则继续使用原文件名。WordPress 文章更新后，下次同步会覆盖该 `wp_id` 对应的文件。

## 命令参数

| 参数 | 说明 |
| --- | --- |
| `--site-url` | WordPress 站点地址，也可以用 `WORDPRESS_URL` 环境变量。 |
| `--username` | WordPress 用户名，也可以用 `WORDPRESS_USERNAME`。 |
| `--password` | WordPress 应用程序密码，也可以用 `WORDPRESS_APP_PASSWORD`。 |
| `--status` | 要同步的文章状态，默认 `publish`；非 `publish` 内容会写为 Hugo 草稿。 |
| `--timezone` | WordPress 本地时间的默认时区，默认 `+08:00`。 |
| `--url-mode` | URL 生成模式，可选 `wp`、`id`、`slug`。 |
| `--content-dir` | Hugo 文章目录，默认 `content/posts`。 |
| `--state-file` | 同步状态文件，默认 `.wordpress-sync-state.json`。 |
| `--skip-comment-count` | 跳过评论数量查询；已有文件会保留原评论数。 |
| `--prune` | 必须配合 `--all`，清理完整 API 结果中不存在的 `wp_id` 文章。 |
| `--dry-run` | 只测试，不写文章文件和状态文件。 |
| `--quiet` | 减少输出。 |
| `--all` | 同步全部符合条件的文章。 |
| `--since-last-run` | 只同步上次同步后修改过的文章。 |
| `--post-id` | 只同步一篇指定 ID 的文章。 |
| `--localize-assets` | 同步后运行 `scripts/localize_remote_assets.py`。 |
| `--build` | 同步后运行 Hugo 构建。 |
| `--build-always` | 即使没有文章变化，也执行资源本地化和构建。 |
| `--hugo-command` | 覆盖默认 Hugo 构建命令。 |

## 环境变量

推荐用环境变量保存站点地址和认证信息。

| 环境变量 | 作用 |
| --- | --- |
| `WORDPRESS_URL` | WordPress 站点地址。 |
| `WP_URL` | `WORDPRESS_URL` 的别名。 |
| `WP_SITE_URL` | `WORDPRESS_URL` 的别名。 |
| `WORDPRESS_USERNAME` | WordPress 用户名。 |
| `WP_USERNAME` | `WORDPRESS_USERNAME` 的别名。 |
| `WORDPRESS_APP_PASSWORD` | WordPress 应用程序密码。 |
| `WP_APP_PASSWORD` | `WORDPRESS_APP_PASSWORD` 的别名。 |
| `WORDPRESS_PASSWORD` | 密码变量别名，建议优先使用应用程序密码。 |

## cron 定时任务

每 10 分钟同步一次并构建：

```cron
*/10 * * * * cd /path/to/hugo-akina-starter && WORDPRESS_URL="https://你的WordPress域名" /usr/bin/python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build >> wordpress-sync.log 2>&1
```

每小时同步一次，不自动构建：

```cron
0 * * * * cd /path/to/hugo-akina-starter && WORDPRESS_URL="https://你的WordPress域名" /usr/bin/python3 scripts/sync_wordpress_api.py --since-last-run >> wordpress-sync.log 2>&1
```

编辑 crontab：

```bash
crontab -e
```

查看日志：

```bash
tail -f wordpress-sync.log
```

## systemd 定时任务

如果部署在 Linux 服务器，也可以用 systemd timer。

Service 示例：

```ini
[Unit]
Description=Sync WordPress posts to Hugo

[Service]
Type=oneshot
WorkingDirectory=/path/to/hugo-akina-starter
Environment=WORDPRESS_URL=https://你的WordPress域名
ExecStart=/usr/bin/python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build
```

Timer 示例：

```ini
[Unit]
Description=Run WordPress to Hugo sync every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Unit=hugo-wordpress-sync.service

[Install]
WantedBy=timers.target
```

启用 timer：

```bash
systemctl enable --now hugo-wordpress-sync.timer
```

查看日志：

```bash
journalctl -u hugo-wordpress-sync.service -f
```

## 常见问题

### REST API 返回 401 或 403

可能原因：

- WordPress 安全插件限制了 REST API。
- 文章接口需要登录。
- 服务器防火墙或 CDN 拦截了 API 请求。
- 用户名或应用程序密码错误。

处理方式：

- 先在浏览器打开 `/wp-json/wp/v2/posts` 检查是否公开可访问。
- 如果需要认证，使用 `WORDPRESS_USERNAME` 和 `WORDPRESS_APP_PASSWORD`。
- 如果安全插件限制接口，把同步服务器 IP 加入白名单。

### REST API 返回 404

可能原因：

- WordPress 固定链接或 REST API 异常。
- 站点不是标准 WordPress。
- 域名填错，或者站点安装在子目录。

处理方式：

- 检查 `WORDPRESS_URL` 是否是 WordPress 站点根地址。
- 打开 `https://你的WordPress域名/wp-json/` 检查 REST API 入口。
- 如果 WordPress 装在 `/blog/`，站点地址应写成 `https://example.com/blog/`。

### 没有新文章被同步

可能原因：

- `.wordpress-sync-state.json` 记录的时间已经是最新。
- WordPress 文章没有更新 `modified_gmt`。
- 文章状态不是 `publish`。

处理方式：

- 使用 `--all --dry-run` 测试全量读取。
- 删除 `.wordpress-sync-state.json` 后重新全量同步。
- 用 `--post-id 文章ID` 测试指定文章。

### 评论数量一直是 0

可能原因：

- WordPress 评论接口关闭。
- 评论接口需要认证。
- 站点没有已审核评论。

处理方式：

- 打开 `/wp-json/wp/v2/comments?post=文章ID&status=approve&per_page=1` 测试。
- 如果不需要评论数量，加 `--skip-comment-count`。

评论接口请求失败时同步会停止，避免把已有评论数误写成 `0`。增量同步只会刷新本次被 WordPress 标记为已修改文章的评论数；如需定期刷新全部评论数，可周期性运行 `--all`。

### 图片仍然引用 WordPress 域名

这是正常行为。同步脚本默认保留 WordPress 正文 HTML，不主动改图片地址。

如果要本地化资源，使用：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets
```

### 手动修改的文章被覆盖

这是预期行为。同一个 WordPress ID 总是更新同一个文件；如果已有 WXR 导入文件，脚本会按 `wp_id` 找到并原位更新。

如果某篇文章想改为 Hugo 手动维护，可以复制成另一个文件，并避免继续同步原 WordPress ID。

## 建议工作流

第一次迁移：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --dry-run
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --all --localize-assets --build
```

日常定时同步：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --since-last-run --localize-assets --build
```

调试单篇文章：

```bash
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --post-id 1269 --dry-run
WORDPRESS_URL="https://你的WordPress域名" python3 scripts/sync_wordpress_api.py --post-id 1269 --localize-assets --build
```
