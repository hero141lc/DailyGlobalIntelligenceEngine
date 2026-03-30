# Daily Global Intelligence Engine (DGIE)

全球科技与金融情报自动汇总系统，支持**全球日报 / 股票情报 / 煤炭情报**等多种模式，通过配置切换数据源、报告格式与推送渠道，无需改代码。

## 项目简介

基于 **GitHub Actions** 的 Serverless 情报机器人：

- **零服务器**：定时在 GitHub 上运行，无需自建机器
- **配置驱动**：通过环境变量切换报告模式（`daily_intel` / `stock` / `coal` / `both`）和推送渠道（邮件 / 飞书 / 企业微信）
- **可扩展**：新增一种情报类型时，只需加配置与对应数据源、报告模板

## 功能特性

### 报告模式（REPORT_MODE）

| 模式 | 说明 | 数据源 | 推送 |
|------|------|--------|------|
| **daily_intel** | 全球科技与金融日报 | 能源、AI、航天、美联储、美股、RSS 快讯等 | 邮件、飞书、企业微信（按 PUSH_CHANNELS） |
| **stock** | 股票情报 | 美股指数、大涨/涨跌个股、美股快讯、SEC、美联储 | 同上 |
| **coal** | 煤炭情报 | 港口煤价、产地坑口、电厂库存、煤炭政策 RSS | 仅企业微信 |
| **both**（默认） | 同时运行日报 + 煤炭 | 先跑 daily_intel 再跑 coal | 日报→邮件/飞书；煤炭→企业微信 |

### 推送渠道（PUSH_CHANNELS）

- **email**：SMTP 发送 HTML 邮件（支持 Gmail 等）
- **feishu**：飞书群机器人 Webhook
- **wecom**：企业微信群机器人 Webhook（Markdown 消息）

### 每日采集内容（daily_intel 模式）

- 马斯克 / 特朗普 最新公开言论
- 欧美电力 / 能源、AI 应用、商业航天、美联储
- 美股主要指数、大涨个股（≥7%）、今日涨跌
- 产业链与涨价、国内科技/华为、储能订单、地缘政治等（Google News RSS）

## 系统架构

```
                    ┌─────────────────────────────────────┐
                    │  config.settings                      │
                    │  REPORT_MODE / PUSH_CHANNELS /       │
                    │  MODE_SOURCES / WECOM_WEBHOOK 等     │
                    └──────────────┬──────────────────────┘
                                   │
  GitHub Actions (定时/手动)        ▼
        │                  ┌──────────────┐
        │                  │ 数据采集      │  按 MODE_SOURCES 只跑启用源
        │                  └──────┬───────┘
        │                         ▼
        └────────────────► 处理（去重/摘要/LLM）
                                   │
                                   ▼
                    ┌──────────────┴──────────────┐
                    │ 报告生成                      │
                    │ daily_intel → HTML           │
                    │ stock / coal → Markdown       │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌──────────────┴──────────────┐
                    │ 推送（按 PUSH_CHANNELS）     │
                    │ email / feishu / wecom       │
                    └─────────────────────────────┘
```

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd <repo-dir>
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量（或 GitHub Secrets）

#### 必需（邮件，若使用 email 通道）

| 变量 | 说明 | 示例 |
|------|------|------|
| SMTP_HOST | SMTP 服务器 | `smtp.gmail.com` |
| SMTP_PORT | 端口 | `587` |
| SMTP_USER | 发件邮箱 | 你的 Gmail |
| SMTP_PASS | 应用密码（Gmail 16 位，无连字符） | 从 Google 账户安全 → 应用密码 获取 |
| EMAIL_TO | 收件人（多个用逗号分隔） | `a@x.com,b@x.com` |

#### 报告模式与推送（通用可配置架构）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| REPORT_MODE | 报告模式 | `daily_intel` |
| PUSH_CHANNELS | 全球日报/股票 的推送通道，逗号分隔 | `email,feishu` |
| COAL_PUSH_CHANNELS | 煤炭报告 的推送通道，逗号分隔 | `wecom` |
| WECOM_WEBHOOK | 群机器人完整 Webhook URL | 空 |
| WECOM_KEY | 群机器人 key（无 URL 时可单独配置） | 空 |
| FEISHU_WEBHOOK_URL | 飞书机器人 Webhook | 空（不推飞书） |

#### LLM（可选，用于摘要与报告总结）

| 变量 | 说明 |
|------|------|
| GITHUB_TOKEN | GitHub Token（Actions 可自动提供） |
| GITHUB_MODEL_NAME | 模型名，默认 `gpt-4o-mini` |

### 4. 本地运行

```bash
# 默认：全球日报，邮件 + 飞书
python main.py

# 仅股票情报并推送到企业微信（需先设 WECOM_WEBHOOK）
set REPORT_MODE=stock
set PUSH_CHANNELS=wecom
python main.py
```

### 5. GitHub Actions 部署

1. 在仓库 **Settings → Secrets and variables → Actions**（或 **Environments → main**）中配置上述变量。
2. 工作流见 [.github/workflows/daily_intelligence.yml](.github/workflows/daily_intelligence.yml)。  
   - 定时：每天 UTC 23:00、05:00（约北京时间 7:00、13:00）  
   - 支持 **workflow_dispatch** 手动触发。

**企业微信配置**（仅群机器人 Webhook）：

- 配置 `WECOM_WEBHOOK`（完整 URL，推荐）或 `WECOM_KEY`（仅 key）。
- 路径：群设置 → 群机器人 → 添加机器人 → 自定义 Webhook。

⚠️ 切勿将 Secret/Key 写进代码或提交到仓库，请使用 GitHub Secrets 或本地 `.env`（并加入 `.gitignore`）。

## 项目结构

```
├── .github/workflows/
│   └── daily_intelligence.yml   # 定时/手动运行
├── main.py                      # 入口：按 MODE 采集 → 报告 → 推送
├── config/
│   └── settings.py             # 配置（含 REPORT_MODE、MODE_SOURCES、PUSH_CHANNELS）
├── sources/                     # 数据采集
│   ├── energy.py, ai.py, space.py, fed.py, stocks.py
│   ├── web_sources.py, commodities_military.py, rss_extra.py, twitter.py
│   └── ...
├── llm/
│   └── github_llm.py            # LLM 摘要与报告总结
├── formatter/
│   ├── report_builder.py        # daily_intel HTML 报告
│   ├── stock_report.py          # stock 模式 Markdown 报告
│   └── coal_report.py          # coal 模式 Markdown 报告（预留）
├── mail/
│   ├── mailer.py                # 邮件发送
│   ├── feishu.py                # 飞书推送
│   └── wecom.py                 # 企业微信推送
├── utils/
│   ├── logger.py, dedup.py, time.py, google_rss.py, ...
└── requirements.txt
```

## 模式与数据源映射（MODE_SOURCES）

在 `config/settings.py` 中可修改各模式启用的数据源：

- **daily_intel**：web_sources, google_rss, energy, commodities_military, ai, space, fed, stocks, rss_extra, twitter
- **stock**：stocks, rss_extra, fed
- **coal**：coal_port, coal_pit, coal_powerplant, coal_policy（预留，需自行实现爬虫并注册到 SOURCE_MODULES）

通过改配置即可支持「只跑股票相关」或未来接入煤炭数据源，无需改主流程。

## 执行时间（GitHub Actions）

- **定时**：每天 UTC 23:00、05:00（约北京 7:00、13:00）
- **手动**：Actions 页选择 workflow → Run workflow

## 注意事项

1. **零成本**：依赖 GitHub Actions 免费额度（每月约 2000 分钟）。
2. **数据源**：均为公开 RSS/API，不爬取需登录内容。
3. **空数据**：若采集或处理后无数据，不会发送邮件、不报错退出。
4. **煤炭模式**：当前 `coal` 模式无真实爬虫，会生成占位报告；后续在 `sources` 下实现 `coal_*` 并在 main 中注册即可接入。

## 扩展方向

- 实现煤炭数据源（港口价、坑口价、电厂库存、政策）与 `coal_report` 模板
- 多 workflow：如单独 `coal_report.yml`，cron 不同、`REPORT_MODE=coal`、`PUSH_CHANNELS=wecom`
- 报告过长时企业微信分条发送

## 许可证

MIT License

## 贡献

欢迎提交 Issue 与 Pull Request。
