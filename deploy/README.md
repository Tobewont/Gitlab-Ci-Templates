# deploy

部署发布：CD API、GitOps、SSH。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.deploy-cd` | - | `deploy/cd/jobs.gitlab-ci.yml` |
| `.deploy-gitops` | - | `deploy/gitops/jobs.gitlab-ci.yml` |
| `.deploy-ssh` | - | `deploy/ssh/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: deploy/cd/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
