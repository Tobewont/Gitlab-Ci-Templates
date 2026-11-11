# ut

单元测试：Go、Python。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.go-ut` | - | `ut/go/jobs.gitlab-ci.yml` |
| `.pytest` | - | `ut/python/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: ut/go/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
