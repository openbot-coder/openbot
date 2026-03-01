# 工作空间使用规范

## 工作空间位置

工作空间位置为: {workspace}。

## 项目结构规范
请严格遵循以下目录结构组织文件：

```
{workspace}/
├── .venv/              # 虚拟环境目录
├── .trash/             # 回收站目录
├── .env                # 环境变量文件
├── .openbot/           # 配置文件目录
│   ├── skills/         # 技能模块目录
│   │   ├── skill1/     # 技能1实现
│   │   └── skill2/     # 技能2实现
│   ├── workflows/      # 工作流定义目录
│   ├── rules/          # 规则目录
│   ├── memory/         # 记忆存储目录
│   │   ├── memory.json     # 记忆数据
│   │   ├── progress.json   # 进度数据
│   │   └── AGENT.md        # 代理配置
│   ├── logs/               # 日志目录
│   ├── config.json     # 主配置文件
│   └── mcp.json        # 模型配置文件
├── drafts/             # 草稿目录
├── resources/          # 资源目录
├── scripts/            # 脚本文件目录
├── crontab/            # 定时任务配置目录
└── project/            # 项目目录
    ├── project1/       # 项目1
    └── project2/       # 项目2
```

**重要**：如发现目录结构不符合规范，请立即通知用户并要求调整。

## 目录说明

- .openbot/：配置文件目录，包含所有配置文件。
- skills/：技能模块目录，包含所有技能模块。
- workflows/：工作流定义目录，包含所有工作流定义。
- rules/：规则目录，包含所有规则。
- memory/：记忆存储目录，包含所有记忆数据。
- logs/：日志目录，包含所有日志文件。
- drafts/：草稿目录，包含所有草稿文件。
- resources/：资源目录，包含所有资源文件。
- scripts/：脚本文件目录，包含所有脚本文件（如Python脚本、Shell脚本等）。
- crontab/：定时任务配置目录，包含所有定时任务配置文件（如cron表达式）。
- project/：项目目录，包含所有项目文件。
- .trash/：回收站目录，包含所有删除的文件。定时清理超过30天的文件。