# common

跨语言通用原子能力：HTTP 上传/下载/请求、SVN 检出、Maven 镜像、包管理镜像、构建过滤、开关跳过。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.build-filter` | - if: '$NEED_BUILD == "true"' | `common/jobs.gitlab-ci.yml` |
| `.http-download` | 用法：extends: .http-download 或 !reference [.http-download, scr | `common/jobs.gitlab-ci.yml` |
| `.http-request` | HTTP_REQUEST_EXPECT_CODE（期望 HTTP 码，默认 200） | `common/jobs.gitlab-ci.yml` |
| `.http-upload` | HTTP_UPLOAD_HEADER    可选，形如 "Authorization: Bearer xxx"（多头请多 | `common/jobs.gitlab-ci.yml` |
| `.maven-settings-setup` | MAVEN_SERVERS: "id1=user1:pass1&id2=user2:pass2"（可选，多组私服凭据） | `common/jobs.gitlab-ci.yml` |
| `.setup-pkg-mirror` | 复用：- !reference [.setup-pkg-mirror, script] | `common/jobs.gitlab-ci.yml` |
| `.skip-if-disabled` | 复用：- !reference [.skip-if-disabled, script] | `common/jobs.gitlab-ci.yml` |
| `.svn-checkout` | 依赖变量：SVN_REPO_URL / SVN_USERNAME / SVN_PASSWORD / SVN_LOCAL_ | `common/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: common/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
