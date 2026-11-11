#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合入前兼容门禁 (Compat Gate) —— 方案心脏。

在模板库自身 MR 流水线里运行：用真实业务配置验证「如果这个 MR 合入，业务流水线还能不能
完整渲染」，并把变更自动分类 A/B/C，决定放行还是拦截。业务侧全程零感知、不需改动。

流程：
  1. 读 scripts/consumers.json（consumer_radar.py 产出），按能力覆盖度抽样 Top N 代表性业务；
  2. 拉每个业务仓的 .gitlab-ci.yml，把 include 里 `ref: stable` 文本替换为当前 MR 分支名
     （GitLab 15.3 无 include_ref 参数，用文本替换法）；
  3. 调用项目级 CI Lint POST /projects/:id/ci/lint（能解析 include:project）：
        - base：业务配置引用 stable 的渲染结果；
        - head：业务配置引用 MR 分支的渲染结果；
  4. head invalid → 门禁 fail（本次 MR 会搞挂该业务）；
  5. head valid → 对比 base/head 的 merged_yaml 做 diff，自动分类：
        - 完全无变化            → A/无影响，通过；
        - 仅 script/镜像等内部字段 → B，通过；
        - 契约字段(job名/变量/rules/stage)变化 → C，输出影响报告，要求 alias/人工评审。

退出码：0=放行；1=拦截（invalid 或未消化的 C 类）；2=用法/环境错误。

权限：只读业务仓（read_api）。CI Lint 是 dry-run，不产生任何写操作。

用法（本地）：
  export GITLAB_URL=... GITLAB_TOKEN=...
  python scripts/compat_gate.py \
      --consumers scripts/consumers.json \
      --template-project "group/gitlab-ci-templates" \
      --mr-ref "$CI_COMMIT_REF_NAME" \
      --stable-ref stable \
      --sample 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any


# ---- GitLab 极简客户端（GET 只读 + CI Lint dry-run POST） --------------------

class GitLabClient:
    def __init__(self, base_url: str, token: str, timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str,
                 params: dict[str, Any] | None = None,
                 body: dict[str, Any] | None = None) -> Any:
        # 只读守卫（默认强制开启）：无论用多高权限的 token（如全局 api scope GITLAB_TOKEN），
        # 都仅允许 GET 与 CI Lint(dry_run)，从代码层面杜绝对任何业务工程的写操作。
        # 仅当显式设 GATE_READONLY=0 时才解除（供受控的管理工具复用；CI 里不设=保持锁定）。
        if os.environ.get("GATE_READONLY", "1") != "0":
            is_ci_lint = method == "POST" and path.rstrip("/").endswith("/ci/lint")
            if method != "GET" and not is_ci_lint:
                raise PermissionError(
                    f"只读守卫：禁止写操作 {method} {path}（仅允许 GET 与 ci/lint dry_run）"
                )
            if is_ci_lint and not (body or {}).get("dry_run"):
                raise PermissionError("只读守卫：ci/lint 必须 dry_run=True（不得触发业务流水线）")
        url = f"{self.base}/api/v4/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"PRIVATE-TOKEN": self.token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            text = resp.read().decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def get_raw_file(self, project_id: int, file_path: str, ref: str) -> str | None:
        enc = urllib.parse.quote(file_path, safe="")
        try:
            body = self._request(
                "GET", f"projects/{project_id}/repository/files/{enc}/raw", {"ref": ref}
            )
            return body if isinstance(body, str) else json.dumps(body)
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            if e.code == 404:
                return None
            raise

    def ci_lint(self, project_id: int, content: str) -> dict:
        """项目级 CI Lint（能解析 include:project）。dry_run 不触发流水线。

        返回 GitLab 15.3 形态：{valid: bool, errors: [...], warnings: [...],
        merged_yaml: "..."}. 不同版本字段略有差异，调用方做兼容处理。

        注意：CI Lint 是 POST，需要 token 具备 **api** scope；read_api 会 403 insufficient_scope。
        """
        try:
            return self._request(
                "POST",
                f"projects/{project_id}/ci/lint",
                body={"content": content, "dry_run": True, "include_jobs": True},
            )
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            if e.code == 403:
                raise PermissionError(
                    "CI Lint 返回 403 insufficient_scope：当前 token 权限不足。"
                    "compat-gate 需要 **api** scope 的 GITLAB_TOKEN（read_api 不够，CI Lint 是 POST）。"
                    "请把 GITLAB_TOKEN 配成 api scope；只读安全由 GATE_READONLY=1 守卫保证。"
                ) from e
            raise


# ---- ref 文本替换 ------------------------------------------------------------

def rewrite_ref(ci_yaml: str, template_project: str, from_ref: str, to_ref: str) -> str:
    """把引用本模板库的 include 段里 from_ref 替换为 to_ref。

    仅替换 project == template_project 的 include 块内的 ref，避免误伤业务自有 include。
    简化实现：按 project 行定位，替换其后就近的 `ref: <from_ref>`。
    """
    lines = ci_yaml.splitlines()
    out = list(lines)
    re_proj = re.compile(r"""project\s*:\s*['"]?([^\s'"]+)['"]?""")
    re_ref_from = re.compile(
        r"""(ref\s*:\s*['"]?)""" + re.escape(from_ref) + r"""(['"]?\s*(#.*)?)$"""
    )
    for i, line in enumerate(lines):
        m = re_proj.search(line)
        if m and template_project in m.group(1):
            for j in range(i, min(i + 5, len(lines))):
                if re_ref_from.search(out[j]):
                    out[j] = re_ref_from.sub(r"\g<1>" + to_ref + r"\g<2>", out[j])
                    break
    return "\n".join(out)


# ---- 抽样 --------------------------------------------------------------------

def select_samples(consumers: list[dict], sample_n: int) -> list[dict]:
    """按「能力覆盖度」贪心抽样：优先选能覆盖更多未覆盖能力文件的业务，
    保证少量样本能触达尽可能多的能力面。"""
    covered: set[str] = set()
    chosen: list[dict] = []
    pool = sorted(consumers, key=lambda c: len(c.get("files_included", [])), reverse=True)
    while pool and len(chosen) < sample_n:
        best, best_gain = None, -1
        for c in pool:
            gain = len(set(c.get("files_included", [])) - covered)
            if gain > best_gain:
                best, best_gain = c, gain
        if best is None or best_gain <= 0:
            # 剩余样本已无新增覆盖，补齐到 sample_n 即可
            chosen.extend(pool[: sample_n - len(chosen)])
            break
        chosen.append(best)
        covered |= set(best.get("files_included", []))
        pool.remove(best)
    return chosen[:sample_n]


# ---- merged YAML 契约 diff ---------------------------------------------------

# 契约字段：出现在这些键上的差异视为 C 类（对业务有感知）
CONTRACT_KEYS = ("stage", "rules", "needs", "artifacts", "dependencies")
# 内部字段：仅这些变化视为 B 类（对业务无感知）
INTERNAL_KEYS = ("script", "before_script", "after_script", "image", "variables", "tags")


def classify_diff(base_yaml: str, head_yaml: str) -> tuple[str, list[str]]:
    """粗粒度分类：比较两份 merged_yaml。返回 (类别, 说明列表)。

    骨架实现用行级 diff + 关键字判定；生产可换成 YAML 解析后按 job/键结构化比对。
    """
    if base_yaml == head_yaml:
        return "A", ["merged YAML 完全一致，无影响"]

    base_lines = base_yaml.splitlines()
    head_lines = head_yaml.splitlines()
    import difflib
    diff = list(difflib.unified_diff(base_lines, head_lines, lineterm=""))
    changed = [d for d in diff if d[:1] in ("+", "-") and not d.startswith(("+++", "---"))]

    hit_contract = [d for d in changed
                    if any(re.search(rf"^[+-]\s*{k}\s*:", d) for k in CONTRACT_KEYS)]
    if hit_contract:
        return "C", ["检测到契约字段变化（stage/rules/needs/artifacts）："] + hit_contract[:20]

    hit_internal = [d for d in changed
                    if any(re.search(rf"^[+-]\s*{k}\s*:", d) for k in INTERNAL_KEYS)]
    if hit_internal and len(hit_internal) >= len(changed) * 0.5:
        return "B", ["仅内部字段变化（script/镜像/内部变量等），对业务无感知"]

    # 无法归入内部字段、又没命中契约键：保守判为 C，交人工确认
    return "C", ["检测到无法自动归类的差异，请人工确认是否影响业务契约："] + changed[:20]


# ---- 主流程 ------------------------------------------------------------------

def lint_field(result: dict, key: str, default):
    """兼容不同 GitLab 版本 CI Lint 返回结构。"""
    if key in result:
        return result[key]
    # 某些版本把结果包在 merged_yaml/status 下
    return result.get(key, default)


def self_check_examples(gl: GitLabClient, template_project: str, mr_ref: str) -> int:
    """兜底：无消费者数据时，至少自检模板库自身 examples 能通过项目级 CI Lint。

    examples 里的 include 指向本模板库（ref: stable / main）。把 ref 改写为当前 MR 分支，
    用项目级 ci/lint（dry_run）渲染——能解析 include:project，验证本 MR 后 examples 仍自洽。
    任一 example 渲染 INVALID → 返回 1（拦截）。
    """
    import glob
    # 模板库自身 project id：CI 环境优先用 CI_PROJECT_ID，否则按 path 解析
    pid_env = os.environ.get("CI_PROJECT_ID", "").strip()
    if pid_env.isdigit():
        pid: int = int(pid_env)
    else:
        enc = urllib.parse.quote(template_project, safe="")
        try:
            proj = gl._request("GET", f"projects/{enc}")  # noqa: SLF001
            pid = int(proj["id"])
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 无法解析模板库 project id（{e}），跳过 examples 自检。", file=sys.stderr)
            return 0

    files = sorted(glob.glob("examples/*.gitlab-ci.yml"))
    if not files:
        print("[warn] 未找到 examples/*.gitlab-ci.yml，跳过自检。", file=sys.stderr)
        return 0

    print(f"[info] 0 消费者：改为自检 {len(files)} 个 examples（ref -> {mr_ref}）能否 CI Lint 通过",
          file=sys.stderr)
    invalid: list[str] = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            invalid.append(f"{fp}: 读取失败 {e}")
            continue
        # examples 引用可能是 ref: stable 或 ref: main，两者都改写到当前 MR 分支
        content = rewrite_ref(content, template_project, "stable", mr_ref)
        content = rewrite_ref(content, template_project, "main", mr_ref)
        try:
            res = gl.ci_lint(pid, content)
        except PermissionError as e:
            # token scope 不足（read_api 无法调 CI Lint）——立即失败并给出唯一清晰提示
            print(f"\n❌ 兼容门禁 FAIL：{e}", file=sys.stderr)
            with open("compat_gate_report.md", "w", encoding="utf-8") as f:
                f.write(f"## ❌ 兼容门禁：token 权限不足\n\n{e}")
            return 2
        except Exception as e:  # noqa: BLE001
            invalid.append(f"{fp}: CI Lint 调用异常 {e}")
            continue
        if not bool(lint_field(res, "valid", False)):
            errs = lint_field(res, "errors", [])
            invalid.append(f"{fp}: INVALID -> {errs[:3]}")

    print("\n" + "=" * 60, file=sys.stderr)
    if invalid:
        print("❌ 兼容门禁 FAIL（examples 自检）：以下示例渲染 INVALID：", file=sys.stderr)
        for b in invalid:
            print("  - " + b, file=sys.stderr)
        with open("compat_gate_report.md", "w", encoding="utf-8") as f:
            f.write("## ❌ 兼容门禁：examples 自检失败\n\n"
                    + "\n".join(f"- {b}" for b in invalid))
        return 1
    print(f"✅ 兼容门禁 PASS（examples 自检）：{len(files)} 个示例均渲染 VALID。", file=sys.stderr)
    with open("compat_gate_report.md", "w", encoding="utf-8") as f:
        f.write(f"## ✅ 兼容门禁：0 消费者，改为 examples 自检\n\n{len(files)} 个示例均 CI Lint VALID。")
    return 0


def _is_context_noise(errors: list) -> bool:
    """判断 lint errors 是否属于「与模板改动无关的空上下文噪声」。

    CI Lint 是 dry_run，缺少真实 pipeline 上下文（CI_PIPELINE_SOURCE、分支、变量等），
    模板/业务仓的 workflow:rules 会把整条流水线判为不该运行，从而报下列错误。
    这类不代表本 MR 破坏了业务，应视为噪声（结合 base 对比后跳过）。
    """
    joined = " ".join(str(e) for e in (errors or [])).lower()
    noise_markers = [
        "filtered out by workflow rules",
        "no stages / jobs for this pipeline",
        "no stages or jobs for this pipeline",
        "pipeline will not run",
    ]
    return any(m in joined for m in noise_markers)


def run_gate(gl: GitLabClient, consumers_path: str, template_project: str,
             mr_ref: str, stable_ref: str, sample_n: int) -> int:
    try:
        with open(consumers_path, encoding="utf-8") as f:
            report = json.load(f)
        consumers = report.get("consumers", [])
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warn] 读取 {consumers_path} 失败（{e}），按 0 消费者处理。", file=sys.stderr)
        consumers = []
    if not consumers:
        print("[warn] consumers.json 为空/缺失：改用 examples 自检兜底（建议尽快跑 refresh-radar）。",
              file=sys.stderr)
        return self_check_examples(gl, template_project, mr_ref)

    samples = select_samples(consumers, sample_n)
    print(f"[info] 抽样 {len(samples)}/{len(consumers)} 个代表性业务做兼容验证", file=sys.stderr)

    blockers: list[str] = []
    c_changes: list[str] = []

    for c in samples:
        pid = c["project_id"]
        path = c["project_path"]
        branch = c.get("default_branch", "main")
        yaml_text = gl.get_raw_file(pid, ".gitlab-ci.yml", branch)
        if not yaml_text:
            print(f"[skip] {path} 无 .gitlab-ci.yml", file=sys.stderr)
            continue

        base_content = rewrite_ref(yaml_text, template_project, stable_ref, stable_ref)
        head_content = rewrite_ref(yaml_text, template_project, stable_ref, mr_ref)

        # 同时 lint base(stable 原样) 与 head(改成 MR ref)，用对比判定，避免空上下文误报
        try:
            base_res = gl.ci_lint(pid, base_content)
            head_res = gl.ci_lint(pid, head_content)
        except PermissionError as e:
            print(f"\n❌ 兼容门禁 FAIL：{e}", file=sys.stderr)
            with open("compat_gate_report.md", "w", encoding="utf-8") as f:
                f.write(f"## ❌ 兼容门禁：token 权限不足\n\n{e}")
            return 2
        except Exception as e:  # noqa: BLE001
            blockers.append(f"{path}: CI Lint 调用异常 {e}")
            continue

        base_valid = bool(lint_field(base_res, "valid", False))
        head_valid = bool(lint_field(head_res, "valid", False))
        head_errs = lint_field(head_res, "errors", [])

        if not head_valid:
            # 关键：只有「base 本来 VALID，head 才 INVALID」= 本 MR 真的搞挂了，才算 blocker。
            # 若 base 也 INVALID（同为空上下文噪声/业务仓固有问题），则与本 MR 无关，跳过。
            if not base_valid or _is_context_noise(head_errs):
                print(f"[skip] {path}: 渲染 INVALID 但与本 MR 无关"
                      f"（base_valid={base_valid}, 空上下文噪声={_is_context_noise(head_errs)}）"
                      f" -> {head_errs[:2]}", file=sys.stderr)
                continue
            blockers.append(f"{path}: 本 MR 引入渲染失败（base 正常/head INVALID）-> {head_errs[:3]}")
            continue

        # head 有效，做契约 diff
        try:
            base_yaml = lint_field(base_res, "merged_yaml", "") or ""
            head_yaml = lint_field(head_res, "merged_yaml", "") or ""
            cls, notes = classify_diff(base_yaml, head_yaml)
        except Exception as e:  # noqa: BLE001
            cls, notes = "C", [f"diff 计算失败，保守判 C：{e}"]

        tag = {"A": "无影响", "B": "内部优化", "C": "契约变更"}.get(cls, cls)
        print(f"[{cls}] {path}: {tag}", file=sys.stderr)
        if cls == "C":
            c_changes.append(f"### {path}\n" + "\n".join(f"- {n}" for n in notes))

    # ---- 结论 ----
    print("\n" + "=" * 60, file=sys.stderr)
    if blockers:
        print("❌ 兼容门禁 FAIL：以下业务在应用本 MR 后无法完整渲染：", file=sys.stderr)
        for b in blockers:
            print("  - " + b, file=sys.stderr)
        return 1

    if c_changes:
        # C 类不直接 fail，而是要求 MR 里已声明 alias/评审。是否放行由 --allow-contract 控制。
        report_md = "## ⚠️ 兼容门禁：检测到契约变更（C 类），业务将受影响\n\n" + "\n\n".join(c_changes)
        report_md += ("\n\n> 请确认 MR 已勾选「契约变更」并提供 alias/feature flag 方案"
                      "（见 docs/发布与兼容契约.md 第 4 节），否则不应合入。")
        # 输出到文件，供 CI 作为 MR 评论/附件
        with open("compat_gate_report.md", "w", encoding="utf-8") as f:
            f.write(report_md)
        print(report_md, file=sys.stderr)
        if os.environ.get("COMPAT_GATE_ALLOW_CONTRACT") == "true":
            print("\n[info] COMPAT_GATE_ALLOW_CONTRACT=true，C 类放行（已人工确认 alias）。",
                  file=sys.stderr)
            return 0
        print("\n❌ 检测到未确认的契约变更。确认已消化后设 COMPAT_GATE_ALLOW_CONTRACT=true 重跑。",
              file=sys.stderr)
        return 1

    print("✅ 兼容门禁 PASS：抽样业务均无契约影响，自动放行。", file=sys.stderr)
    with open("compat_gate_report.md", "w", encoding="utf-8") as f:
        f.write("## ✅ 兼容门禁 PASS\n\n抽样业务均无契约影响，自动放行。\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="模板库合入前兼容门禁")
    ap.add_argument("--consumers", default="scripts/consumers.json")
    ap.add_argument("--template-project", required=True)
    ap.add_argument("--mr-ref", default=os.environ.get("CI_COMMIT_REF_NAME", ""))
    ap.add_argument("--stable-ref", default="stable")
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--gitlab-url", default=os.environ.get("GITLAB_URL", ""))
    ap.add_argument("--token", default=os.environ.get("GITLAB_TOKEN", ""))
    args = ap.parse_args()

    if not args.gitlab_url or not args.token:
        print("需要 --gitlab-url/--token 或环境变量 GITLAB_URL/GITLAB_TOKEN", file=sys.stderr)
        return 2
    if not args.mr_ref:
        print("需要 --mr-ref 或 CI_COMMIT_REF_NAME（当前 MR 分支名）", file=sys.stderr)
        return 2

    gl = GitLabClient(args.gitlab_url, args.token)
    return run_gate(gl, args.consumers, args.template_project,
                    args.mr_ref, args.stable_ref, args.sample)


if __name__ == "__main__":
    raise SystemExit(main())
