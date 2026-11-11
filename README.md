# GitLab CI 公共模板仓库

本仓库只包含**通用原子能力**，不含业务默认组装。业务项目通过 `include` + `extends` 组合出完整流水线。

> **使用边界：默认地址是占位符。**
> 模板里的镜像仓库、Git 项目路径、通知服务和 Sonar 地址默认写成 `example.com` / `registry.example.com` / `group/gitlab-ci-templates`。接入时按自己的环境覆盖对应变量，并在 CI/CD Variables 中注入凭据。

## 文档导航

本库能力繁多，详细说明按主题拆分到 `docs/` 下，README 只作总览与索引：

| 文档 | 内容 |
|---|---|
| [接入使用指南](docs/接入使用指南.md) | 快速接入 5 步、目录结构、关键约定、FAQ、CI 配置防覆盖 |
| [CI 编排与触发](docs/编排与触发.md) | Runner 路由、触发控制、失败允许（卡点）、跨 Stage 并发（DAG） |
| [构建、缓存与镜像约定](docs/构建与镜像.md) | Docker Build 姿势、构建加速与缓存、镜像来源约定 |
| [目录结构与能力清单](docs/能力清单.md) | 完整目录结构、设计原则、各层能力清单、参数约定 |
| [组装示例、Secret 管理与注意事项](docs/组装示例与安全.md) | 业务侧组装示例、Secret 注入、常见注意事项 |
| [发布与兼容契约](docs/发布与兼容契约.md) | 分支拓扑、变更分类、废弃流程、兼容门禁、发布到 stable |
| [分支协作说明](BRANCHING.md) | test → main → stable 三线分支模型与协作流程 |
| [ci-base 基础镜像](docs/ci-base 基础镜像.md) | `CI_BASE_IMAGE` 通用基础镜像的工具集与构建/回滚 |
| [通知渠道对接](docs/通用通知服务对接.md) | 飞书 / 企微 / 钉钉 / 通用 webhook 的接入方式 |

## 快速开始

业务项目在自己的 `.gitlab-ci.yml` 里通过 `include`（统一 `ref: stable`）引入能力，再用 `extends` 组装 job：

```yaml
include:
  - project: 'group/gitlab-ci-templates'
    ref: stable
    file: 'lint/js/jobs.gitlab-ci.yml'
  - project: 'group/gitlab-ci-templates'
    ref: stable
    file: 'notify/jobs.gitlab-ci.yml'

my-eslint:
  extends: .eslint

my-notify:
  extends: .notify
```

更多完整示例见 `examples/`；接入步骤详见 [接入使用指南](docs/接入使用指南.md)。
