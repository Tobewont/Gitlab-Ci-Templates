# download

制品下载：GitLab、OSS、通用 package。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.gitlab-download` | - | `download/gitlab/jobs.gitlab-ci.yml` |
| `.oss-download` | - | `download/oss/jobs.gitlab-ci.yml` |
| `.package-download` | - | `download/package/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: download/gitlab/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
