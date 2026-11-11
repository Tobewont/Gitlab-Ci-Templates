# CI lint/js 专用镜像：预装 eslint + @typescript-eslint 插件 + prettier
#   供 CI 免 npm install（省 eslint/prettier 各 ~30s）
#
# 构建 / 推送：
#   docker login registry.example.com
#   docker build -t registry.example.com/cicd/pipelinecomponents/eslint-tools:node24-eslint8.49 .
#   docker push registry.example.com/cicd/pipelinecomponents/eslint-tools:node24-eslint8.49
#
# 说明：依赖装到固定目录 /opt/lint-tools，通过 NODE_PATH + eslint --resolve-plugins-relative-to
#       让 eslint 在任意工作目录都能解析到这些全局插件（eslint 默认只找项目本地 node_modules）。

FROM registry.example.com/library/node:24.12.0

# 预装目录（与工作目录解耦，避免污染业务项目）
WORKDIR /opt/lint-tools

# 仅复制依赖清单，利用镜像层缓存
COPY package.json ./

# 安装 lint 所需依赖（走国内源加速）
RUN npm install --no-audit --no-fund --registry https://registry.npmmirror.com \
 && npm cache clean --force

# eslint / prettier 可执行文件加入 PATH；插件解析目录用 NODE_PATH 兜底
ENV LINT_TOOLS_DIR=/opt/lint-tools \
    NODE_PATH=/opt/lint-tools/node_modules \
    PATH=/opt/lint-tools/node_modules/.bin:$PATH

# 自检：确认 eslint / prettier / 关键插件目录就位
RUN eslint --version \
 && prettier --version \
 && test -d /opt/lint-tools/node_modules/@typescript-eslint/parser \
 && test -d /opt/lint-tools/node_modules/@typescript-eslint/eslint-plugin \
 && echo "eslint plugins OK"

WORKDIR /
