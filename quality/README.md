# quality

代码质量：SonarQube 扫描/质量门/项目预置、外部报告转 Sonar。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.upload-sonar` | - | `quality/upload-sonar/jobs.gitlab-ci.yml` |
| `.sonar-project-provision` | 用于首次扫描前的项目治理，一般放在 .sonar-scan 之前 | `quality/sonar-provision/jobs.gitlab-ci.yml` |
| `.sonar-quality-gate` | 须在 .sonar-scan 之后执行（消费其产出的 report-task.txt） | `quality/sonar-gate/jobs.gitlab-ci.yml` |
| `.sonar-scan` | - | `quality/sonar-scan/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: quality/upload-sonar/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
