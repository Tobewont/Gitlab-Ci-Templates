#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影响面雷达 (Consumer Radar) —— 只读扫描哪些业务仓库/分支引用了 CI 公共模板库。

作用：产出 consumers.json（模板库消费者地图），服务于两件事：
  1) 合入前兼容门禁 compat_gate.py 的抽样输入；
  2) 废弃决策——某旧契约（变量/hidden job）是否还有人引用，是否可安全删除。

权限：只需 read_api 级别的 token，**永不写业务仓**。请勿使用 admin 写权限。

用法：
  export GITLAB_URL="https://gitlab.example.net"
  export GITLAB_TOKEN="<read_api token>"
  python scripts/consumer_radar.py \
      --groups my-group \
      --template-project "group/gitlab-ci-templates" \
      --out scripts/consumers.json

GitLab 15.3 兼容：仅使用通用 REST API（groups/projects、repository/files raw）。
若集群启用了 Advanced Search（Elasticsearch），可另走全局 Search API scope=blobs 加速，
本骨架默认走稳健的「遍历项目 + 取 .gitlab-ci.yml」路线，几百个仓库 nightly 跑一轮足够。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable


# ---- 与本模板库 include 相关的正则 -------------------------------------------

# 匹配 include:project 块中的 project / ref / file，尽量宽松以覆盖不同缩进与引号风格。
RE_PROJECT = re.compile(r"""project\s*:\s*['"]?([^\s'"]+)['"]?""")
RE_REF = re.compile(r"""ref\s*:\s*['"]?([^\s'"#]+)['"]?""")
RE_FILE = re.compile(r"""file\s*:\s*['"]?([^\s'"]+)['"]?""")
# 业务 job 里 extends 的 hidden job（. 开头）。用于统计每个能力被哪些业务 extends。
RE_EXTENDS = re.compile(r"""extends\s*:\s*\[?\s*['"]?(\.[A-Za-z0-9._-]+)""")


@dataclass
class ConsumerRef:
    """单个业务仓库对模板库的一次引用画像。"""
    project_id: int
    project_path: str
    default_branch: str
    refs_used: list[str] = field(default_factory=list)     # 引用的 ref（main/stable/tag…）
    files_included: list[str] = field(default_factory=list)  # include 的能力文件路径
    hidden_jobs_extended: list[str] = field(default_factory=list)  # extends 的 hidden job


class GitLabClient:
    """极简 GitLab REST 客户端（仅 GET，只读）。

    双重只读保证：(1) 只暴露 GET 语义的方法；(2) _get 内置只读守卫（默认强制开启），
    非 GET 请求直接抛 PermissionError。即便传入 api scope token，也绝不对业务工程写。
    另内置可选限流（max_rps>0 时启用），用于保护 GitLab 实例、平滑突发请求。
    """

    def __init__(self, base_url: str, token: str, timeout: int = 30,
                 max_rps: float = 0.0, readonly: bool = True):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.readonly = readonly
        # 令牌桶式限流：仅当 max_rps>0 时启用；用于削峰、不降低正常并发吞吐。
        self._min_interval = (1.0 / max_rps) if max_rps and max_rps > 0 else 0.0
        self._next_at = 0.0
        self._lock = threading.Lock()

    def _throttle(self) -> None:
        """全局最小请求间隔限流：只在超过设定 RPS 时插入极短等待，平滑突发。"""
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            self._next_at = max(now, self._next_at) + self._min_interval
        if wait > 0:
            time.sleep(wait)

    def _get(self, path: str, params: dict[str, Any] | None = None,
             method: str = "GET") -> tuple[Any, dict[str, str]]:
        # 只读守卫（默认强制开启）：本客户端仅用于只读扫描，绝不对业务工程做写操作。
        # 即便日后误加写调用或注入 api scope token，也从代码层拦死非 GET 请求。
        if self.readonly and method != "GET":
            raise PermissionError(f"consumer_radar 只读守卫：禁止 {method} {path}（仅允许 GET）")
        self._throttle()
        url = f"{self.base}/api/v4/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": self.token}, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read().decode("utf-8")
        try:
            return json.loads(body), headers
        except json.JSONDecodeError:
            return body, headers

    def get_paged(self, path: str, params: dict[str, Any] | None = None) -> Iterable[dict]:
        """按 X-Next-Page 翻页，逐条 yield。"""
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        while True:
            params["page"] = page
            data, headers = self._get(path, params)
            if not isinstance(data, list) or not data:
                break
            yield from data
            next_page = headers.get("x-next-page")
            if not next_page:
                break
            page = int(next_page)
            time.sleep(0.05)  # 轻微退避，别把 API 打爆

    def get_raw_file(self, project_id: int, file_path: str, ref: str) -> str | None:
        """取仓库内某文件原始内容；404 返回 None。"""
        enc = urllib.parse.quote(file_path, safe="")
        try:
            body, _ = self._get(
                f"projects/{project_id}/repository/files/{enc}/raw",
                {"ref": ref},
            )
            return body if isinstance(body, str) else json.dumps(body)
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            if e.code == 404:
                return None
            raise


def list_group_projects(gl: GitLabClient, group: str) -> Iterable[dict]:
    enc = urllib.parse.quote(group, safe="")
    yield from gl.get_paged(
        f"groups/{enc}/projects",
        {"include_subgroups": "true", "archived": "false", "simple": "true"},
    )


def list_all_projects(gl: GitLabClient) -> Iterable[dict]:
    """遍历全实例项目（消费者不限 group 时用；需 token 能看到目标项目，admin 最全）。
    按最近活跃降序，便于早命中在用业务、且部分跑也覆盖高价值仓。"""
    yield from gl.get_paged(
        "projects",
        {"archived": "false", "simple": "true", "order_by": "last_activity_at", "sort": "desc"},
    )


def parse_ci_yaml(text: str, template_project: str) -> tuple[list[str], list[str], list[str]]:
    """从 .gitlab-ci.yml 文本里抽取对本模板库的引用画像。

    返回 (refs, files, extended_hidden_jobs)。仅做文本级解析，不依赖 YAML 库，
    以便对语法不完整/含未解析变量的业务配置也能鲁棒扫描。
    """
    refs: set[str] = set()
    files: list[str] = []
    hidden: set[str] = set()

    # 只关心引用了本模板库的 include 段：按行游走，命中 template_project 后就近取 ref/file
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m_proj = RE_PROJECT.search(line)
        if m_proj and template_project in m_proj.group(1):
            window = "\n".join(lines[i : i + 4])  # project 之后紧跟的几行含 ref/file
            m_ref = RE_REF.search(window)
            if m_ref:
                refs.add(m_ref.group(1))
            m_file = RE_FILE.search(window)
            if m_file:
                files.append(m_file.group(1))

    for m in RE_EXTENDS.finditer(text):
        hidden.add(m.group(1))

    return sorted(refs), files, sorted(hidden)


def _write_report(report: dict, out_path: str) -> None:
    """原子写出报告 JSON（先写临时文件再替换，避免半截文件）。"""
    d = os.path.dirname(out_path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)


def _probe_project(gl: GitLabClient, proj: dict, template_project: str) -> ConsumerRef | None:
    """取单个项目默认分支的 .gitlab-ci.yml 并判定是否为 consumer。供线程池调用。"""
    if proj.get("path_with_namespace", "").endswith(template_project.split("/")[-1]):
        return None  # 跳过模板库自身
    branch = proj.get("default_branch")
    if not branch:
        return None  # 空仓无默认分支
    try:
        text = gl.get_raw_file(proj["id"], ".gitlab-ci.yml", branch)
    except Exception:
        return None  # 单仓失败不中断整轮
    if not text:
        return None
    refs, files, hidden = parse_ci_yaml(text, template_project)
    if not (refs or files):
        return None  # 没引用本模板库
    return ConsumerRef(
        project_id=proj["id"],
        project_path=proj.get("path_with_namespace", ""),
        default_branch=branch,
        refs_used=refs,
        files_included=files,
        hidden_jobs_extended=hidden,
    )


def scan(gl: GitLabClient, groups: list[str], template_project: str,
         max_workers: int = 16, limit: int = 0, checkpoint_out: str = "") -> list[ConsumerRef]:
    # groups 为空 → 全实例遍历（消费者不限 group）；否则只遍历指定 group（含子组）
    if groups:
        proj_iter: Iterable[dict] = (p for g in groups for p in list_group_projects(gl, g))
        print(f"[radar] 扫描模式: 指定 group {groups}", file=sys.stderr)
    else:
        proj_iter = list_all_projects(gl)
        print("[radar] 扫描模式: 全实例遍历（不限 group）", file=sys.stderr)

    # 先去重收集项目列表（limit 用于快速试跑）
    projects: list[dict] = []
    seen: set[int] = set()
    for p in proj_iter:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        projects.append(p)
        if limit and len(projects) >= limit:
            break
    print(f"[radar] 待探测项目 {len(projects)} 个，并发 {max_workers} ...", file=sys.stderr)

    consumers: list[ConsumerRef] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_probe_project, gl, p, template_project): p for p in projects}
        for fut in as_completed(futs):
            done += 1
            if done % 500 == 0:
                print(f"[radar] 已探测 {done}/{len(projects)}，命中 {len(consumers)} ...", file=sys.stderr)
            cr = fut.result()
            if cr is not None:
                consumers.append(cr)
                print(f"[hit] {cr.project_path}  refs={cr.refs_used} files={len(cr.files_included)}",
                      file=sys.stderr)
                # 增量落盘：每命中若干个就写一次，长跑/中断也能留下可用的部分结果
                if checkpoint_out and len(consumers) % 25 == 0:
                    try:
                        _write_report(build_report(sorted(consumers, key=lambda c: c.project_path)),
                                       checkpoint_out)
                    except OSError:
                        pass
    consumers.sort(key=lambda c: c.project_path)
    print(f"[radar] 扫描完成：探测 {len(projects)} 个项目，命中 {len(consumers)} 个消费者。", file=sys.stderr)
    return consumers


def build_report(consumers: list[ConsumerRef]) -> dict:
    """产出 consumers.json：既有明细，也有便于门禁/废弃决策的倒排索引。"""
    file_index: dict[str, list[str]] = {}
    job_index: dict[str, list[str]] = {}
    ref_index: dict[str, list[str]] = {}
    for c in consumers:
        for f in c.files_included:
            file_index.setdefault(f, []).append(c.project_path)
        for j in c.hidden_jobs_extended:
            job_index.setdefault(j, []).append(c.project_path)
        for r in c.refs_used:
            ref_index.setdefault(r, []).append(c.project_path)
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "consumer_count": len(consumers),
        "consumers": [asdict(c) for c in consumers],
        # 倒排索引：某能力文件 / 某 hidden job / 某 ref 被哪些业务引用
        "by_file": {k: sorted(set(v)) for k, v in file_index.items()},
        "by_hidden_job": {k: sorted(set(v)) for k, v in job_index.items()},
        "by_ref": {k: sorted(set(v)) for k, v in ref_index.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描引用 CI 公共模板库的业务仓库")
    ap.add_argument("--groups", default="",
                    help="逗号分隔的目标 group（含子组），如 my-group；留空则全实例遍历（消费者不限 group）")
    ap.add_argument("--template-project", required=True,
                    help="模板库项目路径，如 group/gitlab-ci-templates")
    ap.add_argument("--out", default="scripts/consumers.json", help="输出 JSON 路径")
    ap.add_argument("--gitlab-url", default=os.environ.get("GITLAB_URL", ""))
    ap.add_argument("--token", default=os.environ.get("GITLAB_TOKEN", ""))
    ap.add_argument("--max-workers", type=int, default=int(os.environ.get("RADAR_WORKERS", "16")),
                    help="并发探测线程数（默认 16 / 环境变量 RADAR_WORKERS）")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("RADAR_LIMIT", "0")),
                    help="仅探测前 N 个项目（默认 0=全部，用于快速试跑）")
    ap.add_argument("--max-rps", type=float, default=float(os.environ.get("RADAR_MAX_RPS", "0")),
                    help="全局请求限流上限（每秒请求数）。默认 0=不限流（不拖慢）；"
                         "仅在需要保护 GitLab 实例时设一个上限削峰，不影响正常并发吞吐")
    args = ap.parse_args()

    if not args.gitlab_url or not args.token:
        print("需要 --gitlab-url/--token 或环境变量 GITLAB_URL/GITLAB_TOKEN", file=sys.stderr)
        return 2

    gl = GitLabClient(args.gitlab_url, args.token, max_rps=args.max_rps)
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    consumers = scan(gl, groups, args.template_project,
                     max_workers=args.max_workers, limit=args.limit, checkpoint_out=args.out)
    report = build_report(consumers)

    _write_report(report, args.out)
    print(f"[done] {report['consumer_count']} consumers -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
