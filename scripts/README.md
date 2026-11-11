# scripts —— 模板库治理工具

服务于 `docs/发布与兼容契约.md` 定义的「兼容纪律 + 合入门禁 + 灰度发布」体系。
所有脚本对业务仓库**只读**，禁止使用 admin 写权限。

| 脚本 | 阶段 | 作用 | 状态 |
|---|---|---|---|
| `consumer_radar.py` | P1 | 只读扫描哪些业务仓/分支引用了本模板库，产出 `scripts/consumers.json`（消费者地图 + 倒排索引） | ✅ 可运行骨架 |
| `compat_gate.py` | P1 | MR 阶段：读 consumers.json 抽样代表性业务，文本替换 ref 后调项目级 CI Lint + merged YAML diff，判定 A/B/C 并决定是否放行 | ✅ 可运行骨架 |
| `trigger_seed_pipelines.py` | P2 | main promote 阶段：触发种子项目真实 pipeline 并轮询，全绿才快进推进 stable | ✅ 可运行骨架 |

## 执行入口

模板库自身 `.gitlab-ci.yml` 三个 job 串起整套体系：

| job | 触发时机 | 调用脚本 | 卡点 |
|---|---|---|---|
| `compat-gate` | MR 事件 | `compat_gate.py`（缺 consumers.json 时先跑 radar 兜底） | 硬卡点，不兼容不得合入 |
| `refresh-radar` | 定时 / 手动 | `consumer_radar.py` | allow_failure |
| `promote-stable` | 默认分支（manual） | `trigger_seed_pipelines.py` + 提示发起「快照分支 → stable」的 MR | 硬卡点，种子不绿不发布 |

需在 CI/CD Variables（masked）配置凭据。**URL 复用 base 全局 `GIT_DOMAIN`**（`git.example.com`），脚本自动拼 `https://$GIT_DOMAIN`，无需单独配 `GITLAB_URL`。Token 与只读边界：

- `GITLAB_TOKEN`（**必须 `api` scope**）→ `compat-gate`/`refresh-radar`/`promote-stable` 统一使用。
  CI Lint 是 `POST /ci/lint`，`read_api` 会 403 insufficient_scope，故需 `api`。范围要能覆盖被验证的
  业务仓（消费者不限 group）：用能访问全部业务仓的 PAT（如管理员账号），**不要用模板库工程级
  Project Access Token**（它跨不出本工程，lint 不了别的业务仓）。
  安全由 **只读守卫默认开启** 保证：`compat_gate.py` 从代码层仅放行 GET 与 CI Lint(dry_run)，
  绝不对任何业务工程做写操作；`consumer_radar.py` 客户端物理上只发 GET。
  （如需在受控管理工具里解除守卫可显式设 `GATE_READONLY=0`，CI 里不设=保持锁定。）
- 发布到 stable 走人工 MR + `stable-ref-guard`（stable 保持 No one 直推），**无需任何写/merge token**。
- 可选：`RADAR_GROUPS`（留空=全实例扫描；设值则收窄到指定 group）、`COMPAT_GATE_SAMPLE`、
  `SEED_TIMEOUT`、`RADAR_WORKERS`（并发，默认 16）、`RADAR_LIMIT`（试跑限量）、
  `RADAR_MAX_RPS`（限流上限/秒，默认 0=不限流、不拖慢；仅需保护实例时设上限削峰）。
  种子清单参考 `scripts/seeds.example.json` 复制为 `scripts/seeds.json`。

## consumer_radar.py 快速使用

```bash
export GITLAB_URL="https://<your-gitlab>"
export GITLAB_TOKEN="<read_api token>"      # 只读，勿用 admin
python scripts/consumer_radar.py \
  --groups my-group \
  --template-project "group/gitlab-ci-templates" \
  --out scripts/consumers.json
```

产出的 `consumers.json` 含：
- `consumers[]`：每个业务仓引用了哪些 ref / 能力文件 / extends 了哪些 hidden job；
- `by_file` / `by_hidden_job` / `by_ref`：倒排索引，用于**废弃决策**（某契约引用数是否为 0）和**门禁抽样**。

## 落地顺序

见 `docs/发布与兼容契约.md`。P0：契约文档 + MR 模板 + 雷达骨架 + stable 分支。
P1：门禁脚本接入模板库自身 `.gitlab-ci.yml`（compat-gate job）。P2：灰度 promote（promote-stable job）。
除新建 `stable` 保护分支需在 GitLab 侧操作外，其余均已在本地就位。
