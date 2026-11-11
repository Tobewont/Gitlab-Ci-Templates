# upload

制品上传：Git 制品仓、Harbor、OSS、FTP、Git package。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.ftp-upload` | - | `upload/ftp/jobs.gitlab-ci.yml` |
| `.package-upload` | - | `upload/package/jobs.gitlab-ci.yml` |
| `.harbor-push` | - | `upload/harbor/jobs.gitlab-ci.yml` |
| `.oss-upload` | - | `upload/oss/jobs.gitlab-ci.yml` |
| `.gitlab-upload` | - | `upload/gitlab/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: upload/gitlab/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
