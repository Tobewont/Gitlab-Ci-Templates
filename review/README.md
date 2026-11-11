# review

代码评审：AI 评审、扫描结果汇总。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.ai-review` | AI 代码评审：取变更 → 逐文件调 LLM → POST commits/{sha}/comments 回写行评 | `review/ai/jobs.gitlab-ci.yml` |
| `.scan-summary` | - | `review/scan-summary/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: review/ai/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
