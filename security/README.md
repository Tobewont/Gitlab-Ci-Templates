# security

安全扫描：Trivy/Gitleaks/Semgrep/Checkmarx/JFrog Xray。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.checkmarx` | Checkmarx CxSAST 扫描（走 CxSAST CLI runCxConsole.sh） | `security/checkmarx/jobs.gitlab-ci.yml` |
| `.gitleaks` | GitLeaks 敏感信息扫描 | `security/gitleaks/jobs.gitlab-ci.yml` |
| `.jfrog-xray` | - | `security/jfrog-xray/jobs.gitlab-ci.yml` |
| `.semgrep` | Semgrep 代码模式扫描 | `security/semgrep/jobs.gitlab-ci.yml` |
| `.trivy` | Trivy 镜像漏洞扫描 | `security/trivy/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: security/checkmarx/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
