# lint

多语言静态检查：C++/Go/Java/JS/Lua/PHP/Python。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.checkstyle` | 组装 = 取变更文件 + 禁用则跳过 + 过滤 .java + Checkstyle 官方坐标。项目有 checkstyle.xml 时用项目配置，否则用发行版内置配置。`LINT_JAVA_CHECKSTYLE_SONAR_REPORT=true` 时写 XML 报告。 | `lint/java/jobs.gitlab-ci.yml` |
| `.clang-format` | 原子能力：clang-format 代码格式化检查（不修改代码，仅检查） | `lint/cpp/jobs.gitlab-ci.yml` |
| `.clang-tidy` | - | `lint/cpp/jobs.gitlab-ci.yml` |
| `.cppcheck` | cppcheck 静态分析。镜像 entrypoint 已清空，由 shell 执行 script。 | `lint/cpp/jobs.gitlab-ci.yml` |
| `.eslint` | 组装 = 取变更文件 + 禁用则跳过 + 过滤 .js/.ts/.jsx/.tsx + eslint 命令。声明 eslint-plugin-vue 时再纳入 .vue。 | `lint/js/jobs.gitlab-ci.yml` |
| `.go-import-check` | Go 引用检测（依赖 goimportcheck 工具） | `lint/go/jobs.gitlab-ci.yml` |
| `.go-lint-base` | ── 能力基座：镜像 + 取变更文件（组装 base 能力）────────────────── | `lint/go/jobs.gitlab-ci.yml` |
| `.go-vet` | STEP_ARTIFACT 默认空 → lint 场景不产 JSON；compliance 场景继承时赋值即产 JSON | `lint/go/jobs.gitlab-ci.yml` |
| `.golangci-lint` | 组装 = 禁用则跳过 + 过滤 .go + golangci-lint。`LINT_GO_GOLANGCI_SONAR_REPORT=true` 时另写 JSON 报告。 | `lint/go/jobs.gitlab-ci.yml` |
| `.lint-js-fetch-template-file` | 从 `LINT_JS_PRESET_PROJECT` 拉取模板文件。有 `LINT_JS_GITLAB_TOKEN` 时用它，否则用 `CI_JOB_TOKEN`。 | `lint/js/jobs.gitlab-ci.yml` |
| `.lua-lint` | - | `lint/lua/jobs.gitlab-ci.yml` |
| `.phpstan` | - | `lint/php/jobs.gitlab-ci.yml` |
| `.prettier` | 原子能力：Prettier 前端代码格式化检查（仅检查，不修改） | `lint/js/jobs.gitlab-ci.yml` |
| `.pylint` | 组装 = 取变更文件 + 禁用则跳过 + 过滤 .py + pylint 命令。 | `lint/python/jobs.gitlab-ci.yml` |
| `.revive` | 组装 = 禁用则跳过 + 过滤 .go + revive 命令 → checkstyle 报告。 | `lint/go/jobs.gitlab-ci.yml` |

## 无项目配置时的行为

业务仓无对应配置文件时（项目自带配置时一律优先，不覆盖）：

| 工具 | 无项目配置时 | 控制变量（默认） |
| --- | --- | --- |
| Prettier | 写出模板库默认 `.prettierrc` + `.prettierignore`（printWidth 140 / tabWidth 4 / 双引号） | `LINT_JS_PRETTIER_DEFAULT_CONFIG: "true"` |
| ESLint | 无项目配置时写出默认 `.eslintrc.json` | `LINT_JS_ESLINT_DEFAULT_CONFIG: "true"` |
| clang-format | `-style=file` 且无 `.clang-format` 时跳过；显式指定内置风格（Google/LLVM 等）则照常执行 | `LINT_CPP_CLANG_FORMAT_STYLE: "file"` |
| Checkstyle | 无 `checkstyle.xml` 时用发行版内置 `/google_checks.xml`（UTF-8）。`/sun_checks.xml`、`/openjdk_checks.xml` 可通过 `LINT_JAVA_CHECKSTYLE_BUILTIN` 切换；OpenJDK 规范要求 US-ASCII | `LINT_JAVA_CHECKSTYLE_BUILTIN: "/google_checks.xml"` |
| clang-tidy | 无 `.clang-tidy` 且未指定 `LINT_CPP_CLANG_TIDY_CONFIG` 时跳过 | `LINT_CPP_CLANG_TIDY_CONFIG: ""` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: lint/cpp/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
