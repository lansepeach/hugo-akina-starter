#!/usr/bin/env python3
"""Interactive and scheduled WordPress synchronization manager."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_wordpress_api.py"
CRON_MARKER = "# hugo-akina-starter-wordpress-sync"
SYNC_PATHS = ("content/posts", "assets/css", "static/uploads", "static/remote-assets", "public")


def run(command: list[str], *, check: bool = True, capture: bool = False, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, text=True, input=input_text, capture_output=capture)


def synchronize(*, full: bool = False, prune: bool = False, dry_run: bool = False) -> int:
    command = [sys.executable, str(SYNC_SCRIPT)]
    if full:
        command.append("--all")
    if prune:
        command.append("--prune")
    if dry_run:
        command.append("--dry-run")
    else:
        command.extend(("--localize-assets", "--build"))
    print("执行：" + " ".join(shlex.quote(item) for item in command))
    return run(command, check=False).returncode


def current_branch() -> str:
    return run(["git", "branch", "--show-current"], capture=True).stdout.strip()


def worktree_changes() -> list[str]:
    return run(["git", "status", "--porcelain", "--untracked-files=all"], capture=True).stdout.splitlines()


def default_commit_message() -> str:
    return "同步 WordPress 内容 " + datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def publish(remote: str, branch: str, message: str | None, assume_yes: bool, include_all: bool = False) -> int:
    checked_out = current_branch()
    branch = branch or checked_out
    if not checked_out:
        print("error: 当前不在可推送的 Git 分支上", file=sys.stderr)
        return 1
    if branch != checked_out:
        print(f"error: 当前分支是 {checked_out}，拒绝把提交错误推送到 {branch}", file=sys.stderr)
        return 1
    already_staged = run(["git", "diff", "--cached", "--name-only"], capture=True).stdout.strip()
    if already_staged:
        print("error: 仓库已有暂存文件，请先处理后再使用自动提交：", file=sys.stderr)
        print(already_staged, file=sys.stderr)
        return 1

    status_command = ["git", "status", "--short"]
    if not include_all:
        status_command.extend(("--", *SYNC_PATHS))
    status = run(status_command, capture=True).stdout.strip()
    if status:
        print("将提交以下项目变更：" if include_all else "将提交以下同步相关变更：")
        print(status)
        if not assume_yes and input("确认暂存、提交并推送？[y/N] ").strip().lower() not in {"y", "yes"}:
            print("已取消提交")
            return 0
        run(["git", "add", "-A"] if include_all else ["git", "add", "-A", "--", *SYNC_PATHS])
        staged = run(["git", "diff", "--cached", "--quiet"], check=False)
        if staged.returncode == 1:
            run(["git", "diff", "--cached", "--stat"])
            if not message and not assume_yes:
                message = input(f"提交信息（直接回车使用：{default_commit_message()}）：").strip()
            run(["git", "commit", "-m", message or default_commit_message()])
        elif staged.returncode != 0:
            return staged.returncode
    else:
        print("没有新的同步文件需要提交，将检查并推送当前分支。")

    print(f"推送到 {remote}/{branch}")
    return run(["git", "push", remote, branch], check=False).returncode


def cron_schedule(minutes: int) -> str:
    if minutes in {5, 10, 15, 20, 30}:
        return f"*/{minutes} * * * *"
    if minutes == 60:
        return "0 * * * *"
    if minutes > 60 and minutes % 60 == 0 and minutes <= 720:
        return f"0 */{minutes // 60} * * *"
    if minutes == 1440:
        return "0 3 * * *"
    raise RuntimeError("定时间隔支持 5、10、15、20、30、60、120...720 或 1440 分钟")


def install_cron(minutes: int, auto_push: bool, remote: str, branch: str) -> int:
    source_url = os.environ.get("WORDPRESS_URL", "").strip()
    if not source_url:
        raise RuntimeError("安装 cron 前必须设置 WORDPRESS_URL")
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    hugo = shutil.which("hugo")
    if not hugo:
        raise RuntimeError("找不到 Hugo 可执行文件")
    command = [
        f"WORDPRESS_URL={shlex.quote(source_url)}",
        f"HUGO_COMMAND={shlex.quote(hugo + ' --minify --cleanDestinationDir')}",
        shlex.quote(sys.executable),
        shlex.quote(str(Path(__file__).resolve())),
        "auto", "--yes", "--remote", shlex.quote(remote),
    ]
    if branch:
        command.extend(("--branch", shlex.quote(branch)))
    if auto_push:
        command.append("--auto-push")
    line = f"{cron_schedule(minutes)} cd {shlex.quote(str(ROOT))} && {' '.join(command)} >> {shlex.quote(str(log_dir / 'wordpress-sync.log'))} 2>&1 {CRON_MARKER}"
    current = run(["crontab", "-l"], check=False, capture=True)
    lines = [item for item in current.stdout.splitlines() if CRON_MARKER not in item]
    lines.append(line)
    run(["crontab", "-"], input_text="\n".join(lines) + "\n")
    print("已安装定时任务：")
    print(line)
    return 0


def remove_cron() -> int:
    current = run(["crontab", "-l"], check=False, capture=True)
    lines = [item for item in current.stdout.splitlines() if CRON_MARKER not in item]
    run(["crontab", "-"], input_text=("\n".join(lines) + "\n") if lines else "")
    print("已删除 WordPress 同步定时任务")
    return 0


def interactive(remote: str, branch: str) -> int:
    while True:
        print("\nWordPress -> Hugo 管理\n1. 增量同步、本地化并构建\n2. 提交并推送 Git 平台\n3. 同步构建后提交推送\n4. 全量同步并构建\n5. 预览下架文章清理\n6. 安装或更新 cron\n7. 删除 cron\n0. 退出")
        choice = input("请选择：").strip()
        try:
            if choice == "1":
                synchronize()
            elif choice == "2":
                publish(remote, branch, None, False, True)
            elif choice == "3":
                if synchronize() == 0:
                    publish(remote, branch, None, False, True)
            elif choice == "4":
                synchronize(full=True)
            elif choice == "5":
                synchronize(full=True, prune=True, dry_run=True)
            elif choice == "6":
                raw = input("同步间隔分钟数 [30]：").strip()
                auto_push = input("成功后自动提交并推送？[y/N] ").strip().lower() in {"y", "yes"}
                install_cron(int(raw or "30"), auto_push, remote, branch)
            elif choice == "7":
                remove_cron()
            elif choice == "0":
                return 0
            else:
                print("无效选项")
        except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage WordPress synchronization, Hugo builds and Git publishing.")
    parser.add_argument("command", nargs="?", default="menu", choices=("menu", "sync", "full-sync", "publish", "sync-publish", "prune-preview", "auto", "install-cron", "remove-cron"))
    parser.add_argument("--remote", default=os.environ.get("WP_SYNC_GIT_REMOTE", "origin"))
    parser.add_argument("--branch", default=os.environ.get("WP_SYNC_GIT_BRANCH", ""))
    parser.add_argument("--message")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--auto-push", action="store_true")
    parser.add_argument("--all-changes", action="store_true")
    parser.add_argument("--minutes", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "menu":
            return interactive(args.remote, args.branch)
        if args.command == "sync":
            return synchronize()
        if args.command == "full-sync":
            return synchronize(full=True)
        if args.command == "publish":
            return publish(args.remote, args.branch, args.message, args.yes, args.all_changes)
        if args.command == "sync-publish":
            result = synchronize()
            return result if result else publish(args.remote, args.branch, args.message, args.yes, args.all_changes)
        if args.command == "prune-preview":
            return synchronize(full=True, prune=True, dry_run=True)
        if args.command == "auto":
            changes = worktree_changes()
            if changes:
                print("error: 自动同步已中止，工作区必须完全干净（包括未跟踪文件）：", file=sys.stderr)
                print("\n".join(changes), file=sys.stderr)
                return 1
            result = synchronize()
            return result if result or not args.auto_push else publish(args.remote, args.branch, args.message, True, False)
        if args.command == "install-cron":
            return install_cron(args.minutes, args.auto_push, args.remote, args.branch)
        if args.command == "remove-cron":
            return remove_cron()
        return 1
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
