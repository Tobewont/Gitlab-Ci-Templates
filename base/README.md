# base

流水线基础层：执行镜像、语言环境、全局 token/域名、workflow 规则、公共 job 基座。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.base-job` | - | `base/jobs.gitlab-ci.yml` |
| `.base-prepare` | 仅输出环境变量，无副作用；业务侧可 extends 用作首个信息展示 job，或忽略不用。 | `base/jobs.gitlab-ci.yml` |
| `.pipeline-jobs-fetch` | 脚本片段：定义 `_pipeline_jobs_fetch`，拉取当前 pipeline 全部 job 的 JSON 写入 `JOBS_JSON`（请求失败为 `[]`）；先 `!reference [.pipeline-jobs-fetch, script]` 再在后续 script 调用 | `base/jobs.gitlab-ci.yml` |
| `.workflow-rules` | - | `base/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: base/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
