# compliance

合规检测：语言无关的正则、LLM 与报告外壳。检测脚本由使用方放在 `COMPLIANCE_SCRIPT_DIR`。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.regex-check` | 正则规则检测（语言无关），需在 `COMPLIANCE_SCRIPT_DIR` 下提供 `check_regex.sh` | `compliance/jobs.gitlab-ci.yml` |
| `.llm-check` | LLM 语义检测（语言无关），需提供 `check_llm.sh`，并配置 `LLM_*` | `compliance/jobs.gitlab-ci.yml` |
| `.compliance-report` | 报告聚合与回写（语言无关），需提供 `post_report.sh` 与 `GITLAB_TOKEN` | `compliance/jobs.gitlab-ci.yml` |

脚本缺失时对应 job 自动跳过。

## 用法

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: compliance/jobs.gitlab-ci.yml

my-regex-check:
  extends: .regex-check
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
