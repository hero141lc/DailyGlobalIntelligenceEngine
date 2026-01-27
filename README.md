# Daily Global Intelligence Engine (DGIE)

全球科技与金融情报自动汇总系统

## 项目简介

基于 GitHub Actions 的自动化情报系统，每天定时采集、处理和发送全球科技与金融情报日报。完全零运行成本，无需服务器，无需付费 API（LLM 摘要功能需要 OpenAI API Key，可选）。

## 功能特性

每天自动采集以下 8 个情报板块：

1. **马斯克（Elon Musk）**最新公开言论
2. **特朗普（Donald Trump）**最新公开言论
3. **欧美电力/能源**相关动态
4. **AI 应用**（产品/商业化，排除纯论文）
5. **商业航天**（SpaceX / Starlink / 发射 / 合同）
6. **美联储**（FOMC / 官员表态 / 政策信号）
7. **美股主要指数**（S&P500 / NASDAQ / DOW）
8. **美股大涨个股**（涨幅≥7%）及原因归因

## 系统架构

```
GitHub Actions (定时触发)
    ↓
数据采集层 (RSS / API)
    ↓
结构化处理 (去重 / 过滤)
    ↓
LLM 中文摘要 (可选)
    ↓
报告生成 (HTML 邮件)
    ↓
邮件发送
```

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd daily-intelligence
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets：

#### 必需配置（邮件 - 推荐使用 Gmail）

**推荐使用 Gmail**，因为：
- ✅ 支持基本认证（使用应用密码）
- ✅ 配置简单，稳定可靠
- ✅ 适合自动化场景

**Gmail 配置步骤：**

1. **获取 Gmail 应用密码**：
   - 登录 [Google 账户安全](https://myaccount.google.com/security)
   - 启用两步验证（如果未启用）
   - 进入"应用密码"或"App passwords"
   - 生成新密码（选择"邮件"和"其他设备"）
   - 复制生成的 16 位密码（**无连字符**，格式：`xxxxxxxxxxxxxxxx`）

2. **配置 GitHub Secrets**：
   - `SMTP_HOST`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
   - `SMTP_USER`: 你的 Gmail 邮箱地址（如：`your-email@gmail.com`）
   - `SMTP_PASS`: Gmail 应用密码（16位，无连字符）
   - `EMAIL_TO`: 收件邮箱地址（支持多个收件人）
     - **单个邮箱**：`email@example.com`
     - **多个邮箱（逗号分隔）**：`email1@example.com,email2@example.com`
     - **多个邮箱（JSON 数组）**：`["email1@example.com","email2@example.com"]`

**⚠️ 重要提示**：
- 必须使用**应用密码**，不是账户密码
- 应用密码是 16 位字符，**不包含连字符**
- 应用密码只能查看一次，请妥善保存

**其他邮箱服务**：
- Outlook/Office365：已禁用基本认证，不推荐使用（需要使用 OAuth2，过于复杂）
- 其他邮箱：请查询对应 SMTP 设置

#### 可选配置（LLM 摘要 - 免费方案）

**推荐使用 Hugging Face 免费模型（支持 GitHub Token）：**

- `GITHUB_TOKEN` 或 `HF_TOKEN`: 
  - **方式1**：使用 GitHub Token（需要在 [Hugging Face 设置](https://huggingface.co/settings/account) 中关联 GitHub 账号）
  - **方式2**：直接使用 Hugging Face Token（推荐，在 [这里](https://huggingface.co/settings/tokens) 获取，选择 Read 权限即可）
- `HF_MODEL_NAME`: Hugging Face 模型名称（可选，默认：`Qwen/Qwen2.5-0.5B-Instruct`）

**备选方案（需付费）：**

- `OPENAI_API_KEY`: OpenAI API Key（如配置，会在 Hugging Face 失败时作为备选）

### 3. 本地测试（可选）

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@example.com"
export OPENAI_API_KEY="sk-..."  # 可选

# 运行
python main.py
```

## 项目结构

```
daily-intelligence/
├── .github/
│   └── workflows/
│       └── daily_intelligence.yml  # GitHub Actions 工作流
├── main.py                          # 主程序入口
├── config/
│   └── settings.py                  # 配置管理
├── sources/                         # 数据采集模块
│   ├── twitter.py                   # 马斯克/特朗普
│   ├── energy.py                   # 能源/电力
│   ├── ai.py                       # AI 应用
│   ├── space.py                    # 商业航天
│   ├── fed.py                      # 美联储
│   └── stocks.py                   # 美股市场
├── llm/
│   └── github_llm.py               # LLM 摘要模块
├── formatter/
│   └── report_builder.py           # 报告生成器
├── mail/
│   └── mailer.py                   # 邮件发送
├── utils/                          # 工具模块
│   ├── dedup.py                    # 去重
│   ├── time.py                     # 时间处理
│   └── logger.py                   # 日志
└── requirements.txt                 # Python 依赖
```

## 执行时间

- **定时执行**：每天 UTC 23:00（北京时间早上 7:00）
- **手动触发**：可在 GitHub Actions 页面手动触发

## 数据源

- **Twitter**: Nitter RSS（多个实例自动切换）
- **能源/电力**: EIA、Reuters Energy RSS
- **AI 应用**: TechCrunch、Hacker News API
- **商业航天**: SpaceNews、Reuters Aerospace RSS
- **美联储**: Federal Reserve 官方、Reuters RSS
- **美股市场**: Yahoo Finance API

## 注意事项

1. **零成本运行**：仅使用 GitHub Actions 免费额度（每月 2000 分钟）
2. **数据源合规**：所有数据源均为公开 RSS/API，不爬取需要登录的内容
3. **不存储历史**：仅处理当日信息，不存储历史数据
4. **失败处理**：如果采集失败或处理后无数据，不会发送空邮件

## 邮件格式

邮件采用 HTML 格式，包含：
- 8 个板块按固定顺序组织
- 每条信息包含标题、摘要、来源和原文链接
- 美观的样式和排版

## 扩展方向

未来可扩展功能：
- ⭐ 利好/利空/中性标签
- ⭐ 重要性星级评分
- ⭐ 多源合并同一事件
- ⭐ Telegram / 飞书 / 企业微信推送
- ⭐ 周报/月报自动生成

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

