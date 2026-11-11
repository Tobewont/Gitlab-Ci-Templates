# 分支协作说明（test / main / stable）

本仓库采用 **test → main → stable** 的三线分支模型：新原子能力与业务 example 先在
`test` 开发验证，成熟后通过 MR 合回 `main`（canary 集成线）；`main` 验证通过后经**人工
MR + 门禁**发布到 `stable`（业务唯一推荐引用目标）。业务侧 `include` 一律引用
`ref: stable`，完整发布纪律与兼容契约见 `docs/发布与兼容契约.md`。

> **核心约定：`main` / `test` 的 examples 引用 `ref: stable`，仅当示例依赖的能力尚未发布到
> stable 时才临时写 `ref: main`；「发布到 stable」时把 examples + 所有 README 残留的
> `ref: main` 批量改写为 `ref: stable`。**
> 详见下文「发布到 stable」一节。

## 分支职责

| 分支 | 职责 | 业务是否引用 | examples 的 ref | 稳定性 |
|---|---|---|---|---|
| `test` | 开发前沿。新原子能力（jobs/variables）+ 新 example 先在此开发、CI Lint 验证。持续从 `main` 同步。 | 否 | `ref: stable`（能力未发布时临时 `ref: main`） | 迭代 |
| `main` | canary 集成线。只接受经评审的 MR，合入即集成、跑兼容门禁与灰度验证。 | 过渡期兼容旧引用 | `ref: stable`（能力未发布时临时 `ref: main`） | 稳定 |
| `stable` | **业务唯一推荐引用目标**（`ref: stable`）。保持 No one 直推；只经「快照分支 → stable」的人工 MR + `stable-ref-guard` 门禁进入。 | 是（`ref: stable`） | `ref: stable` | 发布线 |

## 核心规则

1. **test 始终是 main 的前沿**：`test` = 最新 `main` + 尚未合并的新开发。**不允许 test 与 main 长期分叉**。
2. **持续同步**：每次在 test 上开工前，先 `git fetch origin && git rebase origin/main`，
   保证 test 基线是最新 main（避免与 main 新增能力撞车，如 notify 多渠道重构、
   lint/go .go-import-check、lint/cpp .cppcheck 等都是 main 先落地）。
3. **成熟即回合**：能力/example 在 test 验证通过后，发起 MR `test → main`，评审合并。
4. **example 的 include 默认写 `ref: stable`**：业务照抄示例即引用发布线。示例依赖的能力
   尚未发布到 stable 时才临时写 `ref: main`（否则业务照抄会 include 失败），并在该行上方
   注明原因；能力发布后随发布快照改回 `ref: stable`。
5. **发布到 stable 时清理残留 ref**：`main` → `stable` 发布快照里，把 examples 与 README 中
   残留的 `ref: main` 批量改写为 `ref: stable`，由 `stable-ref-guard` 兜底校验
   （见「发布到 stable」一节）。
6. **不在 test 上放最终交付以外的临时物**：脚本、草稿放 `$env:TEMP/opencode` 或 `D:\gitlab_ci`。

## 开发流程（在 test 上）

```
# 1. 同步最新 main
git checkout test
git fetch origin
git rebase origin/main

# 2. 开发：新原子能力 <域>/<能力>/{jobs,variables}.gitlab-ci.yml 或 examples/<业务>.gitlab-ci.yml
#    - 能力文件只定义 hidden job；variables 集中参数，用 [用户可配]/[内部] 注释
#    - example 用 include:project ref: stable + extends + 覆盖变量；Secret 不入库，走 CI/CD Variables
#      （示例依赖的能力尚未发布到 stable 时才临时写 ref: main）

# 3. CI Lint 验证（能解析 include:project 的完整校验）
#    见"验证"一节

# 4. 提交并推 test
git add <files>
git commit -m "feat(<域>): <说明>"
git push origin test    # 首次或已同步：普通 push；rebase 后：需 push -f（团队约定谁负责）

# 5. 成熟后发起 MR: test → main
```

## 发布到 stable

`stable` 是业务唯一推荐引用目标。发布 = 把 `main` 已验证的内容经**人工 MR + 门禁**合入
`stable`，并让 `stable` 上的 examples + README 自洽引用 `ref: stable`。**发布只在 stable 上
落地，不回写 main/test**。

### 发布纪律（约定）

- **main/test 的 examples 默认 `ref: stable`**：仅在示例依赖的能力尚未发布到 stable 时
  才临时写 `ref: main`。
- **合入 stable 时批量改写**：把 **examples + 所有 README** 残留的 include 引用行 `ref: main`
  改成 `ref: stable`，改写只发生在发布快照分支里，不污染 main/test；BRANCHING.md 等
  说明性文字不改。
- **stable 走人工 MR + 门禁**：`stable` 保持 **No one 直推**（CI 也不直推），发布通过
  「从快照分支向 stable 发起 MR → `stable-ref-guard` 绿灯 → Maintainer 合并」落地。
- **兜底**：真实项目（`docs/发布与兼容契约.md` 第 6 节的种子项目）跑绿后才 promote；
  任一失败则 stable 原地不动，事故半径锁定在种子项目。

### 发布动作（快照分支 + 门禁校验）

核心：把 **examples + 所有 README** 的 include 引用行 `ref: main` → `ref: stable` 批量改写，
再由 `scripts/check_stable_refs.py` 校验红线。一键脚本 `bash scripts/release_to_stable.sh`
已封装以下逻辑（示例基于 bash）：

```bash
git fetch origin --prune

# 1. 快照分支：必须基于 origin/stable，再把 main 的内容落进来。
#    stable 与 main 无共同祖先（历次发布都是在 stable 上落内容），
#    若以 origin/main 为基建分支，向 stable 发 MR 会产生大量 add/add 冲突。
git checkout -B release/stable-$(git rev-parse --short origin/main) origin/stable
git checkout origin/main -- .   # 只对齐已跟踪文件内容，不引入本地未跟踪产物

#    examples + 所有 README 的引用行改为 ref: stable
#    只匹配独立成行的引用行 ^\s*ref: main\s*$，天然跳过 BRANCHING.md 叙述
mapfile -t FILES < <( { find examples -name '*.gitlab-ci.yml'; find . -name README.md -not -path './.git/*'; } | sort -u )
for f in "${FILES[@]}"; do sed -i -E 's/^([[:space:]]*)ref: main[[:space:]]*$/ref: stable/' "$f"; done

# 2. 门禁校验：examples + 所有 README 不得再有 ref: main 引用行（红线）
python3 scripts/check_stable_refs.py --root . || { echo "ABORT: 仍有 ref: main 引用行"; exit 1; }

# 3. 提交并推送快照分支（普通分支，不受 stable 保护）
git add -A && git commit -m "release(stable): promote main -> stable"
git push origin HEAD

# 4. 从快照分支向 stable 发起 MR（人工 open）；stable-ref-guard 绿灯后 Maintainer 合并
```

> 红线：合入 stable 的内容里，`examples/**` 与所有 `README.md` 的 include 引用行必须
> 全部是 `ref: stable`、`ref: main`=0。`stable-ref-guard`（MR 目标为 stable 时触发，
> `allow_failure: false`）是硬卡点，出现 `ref: main` 引用行即拦截合并；BRANCHING.md 等
> 说明性 `ref: main` 文字不在校验范围（整行正则天然跳过）。

### stable 保护与同步策略

- **stable 受保护（protected）**：*Allowed to push* = **No one**（谁都不能直推，CI 也不例外）；
  *Allowed to merge* = **Maintainers**；禁止 force push。
- **只经 MR 进入**：发布是「快照分支 → stable」的人工 MR，经 `stable-ref-guard` 绿灯后合并，
  不在 stable 上直接开发、不接受直接 push。
- **发布落地在 stable**：examples + README 的 `ref: stable` 改写只随发布 MR 进入 stable；
  main/test 不回写。

## 验证（本地沙盘 CI Lint）

能力/example 用 `include:project ref: main`，需让 GitLab 能解析 include。本地沙盘做法：

```
# 把当前 test 推成本地沙盘 GitLab 的 group/gitlab-ci-templates 的 main 分支
git push -f <sandbox-remote> test:main
# 对 example 做项目级 CI Lint（POST /projects/:id/ci/lint，能解析 include:project）
# 参考脚本：D:\gitlab_ci\scripts\ci_lint.py
```

约定：**每个 example / 能力合入前必须 CI Lint valid**。注意 GitLab 15.3 lint 对
`expire_in: $VAR days` / `allow_failure: $VAR` 不做变量插值——example override 时用字面量
（如 `expire_in: "7 days"`、`allow_failure: true`）。

## 原子能力开发规范

- 一个能力只解决一类问题（单一职责），`jobs.gitlab-ci.yml` 只暴露 hidden job（`.xxx`）。
- 参数集中在同目录 `variables.gitlab-ci.yml`，`[用户可配]` / `[内部]` 注释区分。
- 能力变量在 `variables.gitlab-ci.yml` 中定义，默认值引用 base 全局变量（如 `"$GIT_DOMAIN"`、`"$GITLAB_TOKEN"`）。`jobs.gitlab-ci.yml` 只使用本能力变量，不直接读写全局变量，也不在脚本里做多层 `${A:-${B}}` 兜底。
- 镜像默认地址是占位符 `registry.example.com`，使用方按自己的仓库覆盖。
- Secret（token/密码/AK）真实值走 GitLab CI/CD Variables（masked）。与 base 同一凭据时，能力变量默认值写 `"$GITLAB_TOKEN"` 这类引用；独立写入凭据保持空默认值。
- 复用优先：能 extends 现有能力就不重复实现；变更文件/跳过/过滤复用 common。
- 新能力落地前先确认 main 是否已有等价能力（main 会先行演进），避免重复造。
