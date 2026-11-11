# checks

合并前检查：CI 配置保护、文件排除、敏感词、DB 事务、文档检测。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.ci-config-guard` | 本 job 仅在 MR 流水线创建（rules 限定）；push 流水线不含本 job，下游同样无需等待。 | `checks/jobs.gitlab-ci.yml` |
| `.db-trans-check` | DB 事务检查 | `checks/jobs.gitlab-ci.yml` |
| `.doc-detect` | 文档必要性检测 | `checks/jobs.gitlab-ci.yml` |
| `.file-exclusion-check` | 文件排除检查（禁止提交某些文件） | `checks/jobs.gitlab-ci.yml` |
| `.sensitive-word-check` | 敏感词检查（执行 `CHECKS_SENSITIVE_WORD_CMD`） | `checks/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: checks/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
