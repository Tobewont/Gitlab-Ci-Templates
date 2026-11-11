#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灰度发布触发器 (Seed Pipeline Trigger) —— P2。

在模板库 main 分支 pipeline 尾部运行：触发一批「种子项目」跑真实 pipeline 并轮询结果。
Lint 只能验证「能渲染」，种子真跑用来验证「能跑绿」。全绿才允许把 stable 快进推进。

流程：
  1. 读种子清单（scripts/seeds.json，格式见 scripts/seeds.example.json）；
  2. 对每个种子调用 POST /projects/:id/pipeline 触发（ref 用种子自己的验证分支）；
  3. 轮询 GET /projects/:id/pipelines/:pipeline_id 直到 success/failed/canceled 或超时；
  4. 全部 success -> 退出码 0（promote-stable job 随后快进 stable）；
     任一失败/超时 -> 退出码 1（stable 原地不动，告警维护者）。

权限：需要对种子项目的触发权限（trigger token 或具备 api scope 的 project token）。
      **不涉及业务生产仓库**；种子项目是 examples/ 落地的专用冒烟工程。

用法：
  export GITLAB_URL=... GITLAB_TOKEN=...
  python scripts/trigger_seed_pipelines.py --seeds scripts/seeds.json --timeout 1800
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


TERMINAL_OK = {"success"}
TERMINAL_BAD = {"failed", "canceled", "skipped"}


class GitLabClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.base}/api/v4/{path.lstrip('/')}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"PRIVATE-TOKEN": self.token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def trigger_pipeline(self, project_id: int | str, ref: str,
                         variables: dict[str, str] | None = None) -> dict:
        pid = urllib.parse.quote(str(project_id), safe="")
        body: dict[str, Any] = {"ref": ref}
        if variables:
            body["variables"] = [{"key": k, "value": v} for k, v in variables.items()]
        return self._request("POST", f"projects/{pid}/pipeline", body)

    def get_pipeline(self, project_id: int | str, pipeline_id: int) -> dict:
        pid = urllib.parse.quote(str(project_id), safe="")
        return self._request("GET", f"projects/{pid}/pipelines/{pipeline_id}")


def poll_all(gl: GitLabClient, running: list[dict], timeout: int, interval: int) -> bool:
    """轮询所有已触发流水线直到全部终态或超时。返回是否全绿。"""
    deadline = time.time() + timeout
    pending = {r["_seed"]: r for r in running}
    results: dict[str, str] = {}
    while pending and time.time() < deadline:
        time.sleep(interval)
        for seed, r in list(pending.items()):
            try:
                p = gl.get_pipeline(r["project_id"], r["pipeline_id"])
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 查询 {seed} 流水线异常：{e}", file=sys.stderr)
                continue
            status = p.get("status", "")
            if status in TERMINAL_OK or status in TERMINAL_BAD:
                results[seed] = status
                pending.pop(seed)
                print(f"[done] {seed}: {status}  {p.get('web_url','')}", file=sys.stderr)
            else:
                print(f"[.] {seed}: {status}", file=sys.stderr)

    # 超时未终态的记为失败
    for seed in pending:
        results[seed] = "timeout"

    all_ok = all(s in TERMINAL_OK for s in results.values())
    print("\n" + "=" * 50, file=sys.stderr)
    for seed, s in results.items():
        flag = "✅" if s in TERMINAL_OK else "❌"
        print(f"  {flag} {seed}: {s}", file=sys.stderr)
    return all_ok


def main() -> int:
    ap = argparse.ArgumentParser(description="触发种子项目真实 pipeline 并轮询")
    ap.add_argument("--seeds", default="scripts/seeds.json")
    ap.add_argument("--timeout", type=int, default=1800, help="总超时秒数")
    ap.add_argument("--interval", type=int, default=15, help="轮询间隔秒数")
    ap.add_argument("--gitlab-url", default=os.environ.get("GITLAB_URL", ""))
    ap.add_argument("--token", default=os.environ.get("GITLAB_TOKEN", ""))
    args = ap.parse_args()

    if not args.gitlab_url or not args.token:
        print("需要 --gitlab-url/--token 或环境变量 GITLAB_URL/GITLAB_TOKEN", file=sys.stderr)
        return 2
    if not os.path.exists(args.seeds):
        print(f"种子清单不存在：{args.seeds}（参考 scripts/seeds.example.json）", file=sys.stderr)
        return 2

    with open(args.seeds, encoding="utf-8") as f:
        seeds = json.load(f).get("seeds", [])
    if not seeds:
        print("[warn] 种子清单为空，跳过灰度验证（不阻断）。", file=sys.stderr)
        return 0

    gl = GitLabClient(args.gitlab_url, args.token)
    running: list[dict] = []
    for s in seeds:
        name = s.get("name") or str(s.get("project"))
        try:
            p = gl.trigger_pipeline(
                s["project"], s.get("ref", "main"), s.get("variables"),
            )
            running.append({
                "_seed": name,
                "project_id": s["project"],
                "pipeline_id": p["id"],
            })
            print(f"[trigger] {name}: pipeline {p['id']} {p.get('web_url','')}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[error] 触发 {name} 失败：{e}", file=sys.stderr)
            return 1

    all_ok = poll_all(gl, running, args.timeout, args.interval)
    if all_ok:
        print("\n✅ 全部种子项目通过，允许 promote stable。", file=sys.stderr)
        return 0
    print("\n❌ 存在未通过的种子项目，stable 保持不动。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
