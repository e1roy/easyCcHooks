# CLAUDE.md

## 项目概述

本项目包含 **EasyCcHooks** — 一个单文件 Claude Code Hooks 框架，用于拦截、验证、监控 Claude Code 的工具调用。

- 语言: Python 3.13
- 包管理: uv (Astral)
- 框架核心: `.claude/hooks/easyCcHooks.py` (单文件，包含数据模型 + 接口 + 注册中心 + 执行器 + CLI)

## 目录结构

```text
.claude/
├── settings.json                  # Claude Code 配置 (hooks 自动生成)
└── hooks/
    ├── easyCcHooks.py             # 框架核心 (~930 行)
    ├── example_hooks.py           # 生产 hook (从 tests/ 复制)
    ├── *.py                       # 用户自定义 hook (放这里自动加载)
    ├── README.md                  # 使用文档
    ├── ARCHITECTURE.md            # 架构文档
    └── tests/                     # 测试目录 (scan 时不加载, test 命令会加载)
        ├── example_hooks.py       # 示例 hook 源文件
        ├── test_hooks.py          # 测试脚本
        ├── test_input_*.json      # 测试输入文件
        └── README.md              # 测试说明
```

## 常用命令

```bash
# Hook 管理 (在 .claude/hooks/ 目录下执行)
python3 easyCcHooks.py scan                                    # 扫描并注册 hook
python3 easyCcHooks.py list                                    # 列出已注册 hook
python3 easyCcHooks.py update-config                           # 更新 settings.json
python3 easyCcHooks.py test <HookName> --input <file.json>     # 测试 hook
python3 easyCcHooks.py execute <HookName>                      # 执行 hook (Claude Code 内部调用)

# 测试
python3 easyCcHooks.py test ValidateBashCommand --input tests/test_input_dangerous.json
python3 easyCcHooks.py test ValidateBashCommand --input tests/test_input_safe.json
python3 easyCcHooks.py test InjectContext --input tests/test_input_session.json
```

## 框架关键设计

### Hook 类型 (10 种接口)

| 接口 | 触发时机 |
| ---- | -------- |
| IPreToolUse | 工具调用前 |
| IPostToolUse | 工具调用后 |
| IPermissionRequest | 权限请求时 |
| IUserPromptSubmit | 用户提交提示词时 |
| INotification | 系统通知时 |
| IStop | 会话停止时 |
| ISubagentStop | 子代理停止时 |
| IPreCompact | 上下文压缩前 |
| ISessionStart | 会话开始时 |
| ISessionEnd | 会话结束时 |

### ToolName 枚举

`ToolName(str, Enum)` 定义了所有 Claude Code 工具名称，用于 hook 的 `matcher` 属性：

- 文件操作: `Bash`, `Read`, `Write`, `Edit`, `NotebookEdit`
- 搜索: `Glob`, `Grep`
- 网络: `WebFetch`, `WebSearch`
- 代理: `Task`, `TodoWrite`
- 交互: `AskUserQuestion`, `EnterPlanMode`
- 团队: `SendMessage`, `TeamCreate`, `TeamDelete`
- 其他: `Skill`, `All` (通配符 `*`)

### 当前已激活的 Hook

配置在 `.claude/settings.json` 中，由 `update-config` 自动生成：

> `update-config` 仅替换 easyCcHooks 自动托管的命令项（`python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/easyCcHooks.py execute ...`），会清理失效托管项，并保留用户手写的 hooks 配置。

| Hook | 类型 | 匹配 | 功能 |
| ---- | ---- | ---- | ---- |
| ValidateBashCommand | PreToolUse | Bash | 阻止危险命令 (rm -rf /)，sudo 需确认 |
| WatchPreToolUse | PreToolUse | * | 记录所有工具调用到 watch.log |
| InjectContext | SessionStart | — | 会话启动时注入项目信息 |

### 开发新 Hook 的流程

1. 在 `.claude/hooks/` 下创建 `.py` 文件，继承对应接口
2. 实现 `execute()` 方法
3. 运行 `python3 easyCcHooks.py scan` 确认注册
4. 运行 `python3 easyCcHooks.py update-config` 写入配置
5. 重启 Claude Code 生效

## 开发约定

- 使用中文撰写描述和文档
- 使用 Markdown 格式
- 框架代码集中在 `easyCcHooks.py` 单文件中，不要拆分
- Hook 实现文件放在 `.claude/hooks/` 目录或其子目录下 (支持 rglob 递归扫描)
- `matcher` 属性优先使用 `ToolName` 枚举而非硬编码字符串
- 导入统一使用 `from easyCcHooks import ...`

## 依赖

仅使用 Python 标准库，无第三方依赖。
