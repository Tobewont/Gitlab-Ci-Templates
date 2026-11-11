# database

MySQL 原子操作：查询、执行。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.mysql-exec` | 安全：autocommit=False；异常即回滚；行数不符即回滚；锁在 finally 释放 | `database/mysql/jobs.gitlab-ci.yml` |
| `.mysql-query` | 安全：连接变量缺失 fail-closed；参数全占位转义；密码不打印 | `database/mysql/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: database/mysql/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
