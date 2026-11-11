# git

Git/GitLab 原子能力：变更文件、MR 操作、评论、认证、版本号。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.changes` | 用法：changes: { extends: .changes }，下游 job needs: [changes] | `git/changed-files/jobs.gitlab-ci.yml` |
| `.close-mr` | GIT_MR_CLOSE_IID（默认走 $CI_MERGE_REQUEST_IID；非 MR 事件时用于跨 job 传递） | `git/mr/jobs.gitlab-ci.yml` |
| `.filter-changed-files` | 输出：STEP_MATCHED_FILES | `git/changed-files/jobs.gitlab-ci.yml` |
| `.get-changed-files` | 结果导出到 CI_CHANGED_FILES。 | `git/changed-files/jobs.gitlab-ci.yml` |
| `.get-changed-folders` | 输出：CI_CHANGED_FOLDERS（去重，逗号分隔） | `git/changed-files/jobs.gitlab-ci.yml` |
| `.get-commit-keyword` | 导出：CI_MATCHED_COMMIT_MESSAGE（若命中；未命中则为空） | `git/version/jobs.gitlab-ci.yml` |
| `.get-mr-diff` | 然后能力脚本读 $GIT_MR_DIFF_FILE | `git/mr/jobs.gitlab-ci.yml` |
| `.git-comment` | ── 评论 job 基座：纯 API 调用，无需源码 ── | `git/comment/jobs.gitlab-ci.yml` |
| `.git-comment-post` | ── 发送片段：读 body → POST 到 MR notes / Commit comments ── | `git/comment/jobs.gitlab-ci.yml` |
| `.git-describe` | GIT_VERSION_DESCRIBE_ARGS（可选：git describe 附加参数，默认 --long --t | `git/version/jobs.gitlab-ci.yml` |
| `.git-https-auth` | 为 Git HTTPS 写入认证（GIT_DOMAIN + GITLAB_USERNAME + GITLAB_TOKEN），供后续 clone / 私有依赖使用 | `git/auth/jobs.gitlab-ci.yml` |
| `.merge-mr` | 说明：合并被拒（如 pipeline 未成功 / 存在冲突 / 无权限 / MR 非 opened）时 curl 返回非 | `git/mr/jobs.gitlab-ci.yml` |
| `.submodule-checkout` | 用 base 层 Git 认证递归检出私有子模块 | `git/auth/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: git/auth/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
