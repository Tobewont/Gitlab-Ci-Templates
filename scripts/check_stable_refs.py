#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stable 分支引用门禁 (Stable Ref Guard)。

在「MR 目标分支 = stable」的流水线里运行，只读校验：合并进 stable 的内容里，
examples/ 与所有 README.md 的 include 引用行不得再指向 ref: main —— 必须全部是
ref: stable。守住「stable 分支对外引用恒为 stable」这条红线。

校验范围（与发布快照改写范围一致）：
  - examples/**/*.gitlab-ci.yml
  - 仓库根与各子目录的 README.md
  只针对「独立成行的 include 引用行」：正则 ^\\s*ref:\\s*main\\s*$
  BRANCHING.md 及任何非独立成行的说明性 "ref: main" 文字不在范围内（不会误伤）。

退出码：
  0 = 通过（范围内无 ref: main 残留）
  1 = 拦截（发现 ref: main 引用行，打印文件:行号:内容）
  2 = 用法/环境错误

用法：
  python3 scripts/check_stable_refs.py            # 校验当前工作区
  python3 scripts/check_stable_refs.py --root .   # 指定仓库根
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# 独立成行的 include 引用行：仅缩进 + "ref: main"，行尾无其它内容。
# 这样只命中 YAML include 块里的引用，跳过 Markdown 叙述里的行内 `ref: main`。
REF_MAIN_LINE = re.compile(r"^\s*ref:\s*main\s*$")


def iter_target_files(root: str):
    """产出需要校验的文件相对路径：examples/** 下的流水线文件 + 所有 README.md。"""
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过 .git 与常见工作目录，避免误扫
        dirnames[:] = [d for d in dirnames if d not in (".git", ".agnes", ".work_fgui")]
        rel_dir = os.path.relpath(dirpath, root)
        for fn in filenames:
            rel = os.path.normpath(os.path.join(rel_dir, fn)).replace(os.sep, "/")
            if rel.startswith("./"):
                rel = rel[2:]
            in_examples = rel.startswith("examples/") and rel.endswith(".gitlab-ci.yml")
            is_readme = fn == "README.md"
            if in_examples or is_readme:
                yield rel


def scan_file(path: str):
    """返回命中行列表 [(lineno, text)]。"""
    hits = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if REF_MAIN_LINE.match(line.rstrip("\r\n")):
                    hits.append((i, line.rstrip("\r\n")))
    except OSError as e:
        print(f"[error] 无法读取 {path}: {e}", file=sys.stderr)
        raise
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="stable 分支 include 引用门禁")
    ap.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"[error] root 不是目录: {root}", file=sys.stderr)
        return 2

    total_files = 0
    offenders = {}
    for rel in sorted(iter_target_files(root)):
        total_files += 1
        hits = scan_file(os.path.join(root, rel))
        if hits:
            offenders[rel] = hits

    if offenders:
        n = sum(len(v) for v in offenders.values())
        print("=" * 70)
        print(f"[FAIL] 检测到 {n} 处 'ref: main' 引用行（{len(offenders)} 个文件）——")
        print("       合入 stable 前，examples 与 README 的 include 引用必须是 ref: stable。")
        print("=" * 70)
        for rel in sorted(offenders):
            for lineno, text in offenders[rel]:
                print(f"  {rel}:{lineno}: {text.strip()}")
        print("-" * 70)
        print("修复：从「发布快照分支」发起 MR（其 examples+README 已批量改为 ref: stable），")
        print("      而不是从裸 main 发起。可用 scripts/release_to_stable.sh 生成快照分支。")
        return 1

    print(f"[OK] 已扫描 {total_files} 个目标文件（examples + 所有 README），"
          f"无 'ref: main' 引用行残留，stable 引用红线通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
