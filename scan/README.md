# scan

跨仓批量扫描调度：发现活跃工程/活跃分支，拉代码后在工程目录执行扫描脚本。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.active-repos-discover` | 只读 GitLab API 发现活跃工程与活跃分支，产出清单 JSON 与 `SCAN_ACTIVE_PROJECT_COUNT` / `SCAN_ACTIVE_TARGET_COUNT` dotenv | `scan/active-repos/jobs.gitlab-ci.yml` |
| `.active-repos-scan` | 消费清单，逐「工程+分支」组合 clone 后在工程根目录执行 `SCAN_ACTIVE_NPX_CMD`；组合间失败隔离，末尾统一汇总 | `scan/active-repos/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: scan/active-repos/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。

## 职责边界

- 本能力只做**调度**：发现活跃工程/分支 → 拉代码 → 在工程目录执行命令 → 汇总记录。
- **扫描规则、结果处理与上传**全部由 `SCAN_ACTIVE_NPX_CMD` 指向的 npx 包自身实现，能力不感知。
- **定时（如一周一次）不在本能力内配置**：由业务项目 `.gitlab-ci.yml` 的 `workflow.rules` 放行
  `$CI_PIPELINE_SOURCE == "schedule"`，并在项目 Settings → CI/CD → Pipeline schedules 建计划。

## 扫描范围

| 配置 | 行为 |
|---|---|
| `SCAN_ACTIVE_GROUPS: ""`（默认） | **全局扫描**：`GET /projects`，覆盖 token 可见的所有工程（含个人命名空间） |
| `SCAN_ACTIVE_GROUPS: "a,b/c"` | 仅扫这些 group（`SCAN_ACTIVE_INCLUDE_SUBGROUPS` 控制是否含子 group） |

全局扫描时可用 `SCAN_ACTIVE_MEMBERSHIP_ONLY: "true"` 收窄为"我是成员的工程"。
两种模式都走服务端 `last_activity_after` 过滤，只拉窗口内活跃的工程，不会全量翻页。

## 活跃判定口径

| 维度 | 变量 | 默认 | 口径 |
|---|---|---|---|
| 扫描范围 | `SCAN_ACTIVE_GROUPS` | `""` | 留空 = 全局；指定 = 仅这些 group |
| 活跃窗口 | `SCAN_ACTIVE_WINDOW_DAYS` | `7` | 天数，工程与分支共用同一窗口 |
| 活跃工程 | `SCAN_ACTIVE_PROJECT_TOP_N` | `0` | `0` = 窗口内所有活跃工程；`N>0` = 最活跃的前 N 个 |
| 活跃分支 | `SCAN_ACTIVE_BRANCH_TOP_N` | `1` | `1` = 仅默认分支；`0` = 所有活跃分支；`N>1` = 默认分支 + 最活跃的 (N-1) 个 |

### 分支选取规则（重点）

`SCAN_ACTIVE_BRANCH_TOP_N` 的语义是**默认分支保底 + 其余按活跃度补齐**，不是单纯按提交数取前 N：

| 取值 | 选中的分支 |
|---|---|
| `1`（默认） | 只有默认分支。默认分支窗口内无提交 → 该工程整体跳过 |
| `0` | 该工程窗口内所有活跃分支，不限个数 |
| `N>1` | 默认分支（若窗口内有提交）+ 其余分支中提交数最多的 (N-1) 个，共最多 N 个 |

举例：某工程默认分支 `main` 窗口内仅 3 次提交，另有 `dev`(30 次)、`qa`(18 次)。

- `BRANCH_TOP_N=2` → `main` + `dev`（`main` 保底占位，即便它提交数最少）
- `BRANCH_TOP_N=3` → `main` + `dev` + `qa`
- `BRANCH_TOP_N=1` → 仅 `main`

若默认分支窗口内无提交，则不占名额：`N>1` 时取最活跃的 (N-1) 个，`N=1` 时该工程跳过。
`SCAN_ACTIVE_BRANCH_STRATEGY=default-branch` 等价于 `BRANCH_TOP_N=1`。

### 工程选取规则

工程活跃度 = **该工程窗口内提交数最多的那个分支的提交数**（与分支是否入选无关），并列时最后活动
时间更新者优先。注意这与分支选取相互独立：`gamma` 的 `main` 只有 3 次提交，但其 `dev` 有 30 次，
所以 `gamma` 的工程活跃度是 30。

| 其他维度 | 说明 |
|---|---|
| Top N 不足 | 工程或分支实际数量少于 N 时取实际数量，不报错 |
| 分支预筛 | 分支最后提交在窗口外 → 直接淘汰（不统计提交数，省 API 请求） |
| `BRANCH_TOP_N=1` 优化 | 只需默认分支时，其余分支完全不发提交统计请求 |

三个维度相互独立，可自由组合。例如「近 14 天最活跃的 20 个工程，每个扫默认分支 + 4 个最活跃分支」：

```yaml
variables:
  SCAN_ACTIVE_WINDOW_DAYS: "14"
  SCAN_ACTIVE_PROJECT_TOP_N: "20"
  SCAN_ACTIVE_BRANCH_TOP_N: "5"
```

> `SCAN_ACTIVE_MAX_PROJECTS` 与 `SCAN_ACTIVE_PROJECT_TOP_N` 的分工：前者是**拉取阶段**按最后活动
> 时间的硬上限（安全阀，防一次拉爆 API）；后者是**统计完提交数后**按真实活跃度的择优截断。
> 两者可同时生效，`MAX_PROJECTS` 先粗筛、`PROJECT_TOP_N` 再择优。

## 清单与计数口径

工程或分支 Top N 生效时，同一工程可能产出多条记录，因此需区分两个计数：

| 计数 | 含义 | 出口 |
|---|---|---|
| 工程数 | 择优后的活跃工程个数 | dotenv `SCAN_ACTIVE_PROJECT_COUNT`、清单 `project_count`、结果 JSON `project_count` |
| 组合数 | 「工程+分支」组合个数，即下游实际执行次数 | dotenv `SCAN_ACTIVE_TARGET_COUNT`、清单 `total`、结果 JSON `total` |

清单 `projects[]` 每项是一个「工程+分支」组合，含 `branch_rank`（1 = 默认分支若入选，其后按提交数
排序）与 `is_default_branch`；清单头部另有 `project_top_n` / `branch_top_n` 记录本次生效的择优参数。
下游 `rules` 判空请用 `SCAN_ACTIVE_TARGET_COUNT`（实际执行次数），而非工程数。

## 失败隔离与记录

- 每个「工程+分支」组合在独立子进程 + 独立工作目录中执行，`timeout $SCAN_ACTIVE_TIMEOUT_SECONDS` 硬超时（超时记 `exit=124`）。
- 任一组合 clone/npx 失败**不中断**其它组合；同一工程的 Top N 个分支之间同样互不影响。
- 工作目录与日志文件名含分支（形如 `grp_alpha@feature_a`），同工程多分支不会互相覆盖；
  分支名含非 ASCII 字符（如中文）时自动追加短哈希，避免字符替换后两个分支撞名。
- job 末尾统一打印汇总表 + 失败项日志尾部；产出 `$SCAN_ACTIVE_RESULT_FILE` 与 `$SCAN_ACTIVE_LOG_DIR/` artifacts。
- 默认 `SCAN_ACTIVE_FAIL_ON_ERROR: "false"`（有失败也不阻断，只做记录）；需要卡点时业务侧覆盖为 `"true"`。

## 传给扫描脚本的上下文环境变量

`SCAN_ACTIVE_NPX_CMD` 执行时 cwd 为工程根目录，可直接读以下变量：

| 变量 | 含义 |
|---|---|
| `SCAN_PROJECT_ID` / `SCAN_PROJECT_PATH` / `SCAN_PROJECT_URL` | 工程 ID / 带命名空间路径 / 仓库地址 |
| `SCAN_BRANCH` / `SCAN_COMMIT_SHA` | 本次扫描的分支与其 HEAD commit |
| `SCAN_BRANCH_RANK` | 该分支在本工程内按提交数的排名（1 = 最活跃） |
| `SCAN_BRANCH_COMMIT_COUNT` | 该分支窗口内提交数 |
| `SCAN_WINDOW_DAYS` / `SCAN_WINDOW_SINCE` | 活跃窗口天数与起始时间（ISO8601 UTC） |

## Token 权限

统一复用 base 层全局 `GITLAB_TOKEN`（项目/Group CI/CD Variables masked 注入）：

- `.active-repos-discover` 需 `read_api`（仅 GET，脚本内不存在任何写调用）
- `.active-repos-scan` 需 `read_repository`（clone 走 askpass 供给凭据，token 不进 URL、不进日志）
