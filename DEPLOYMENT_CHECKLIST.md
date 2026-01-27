# 部署检查清单

## ✅ GitHub Secrets 配置检查

### 必需配置（邮件）

请确认以下 Secrets 已正确配置，**名称必须完全匹配**：

- ✅ `SMTP_HOST` - Gmail 使用 `smtp.gmail.com`（可选，有默认值）
- ✅ `SMTP_PORT` - Gmail 使用 `587`（可选，有默认值）
- ⚠️ `SMTP_USER` - 你的 Gmail 邮箱地址
- ⚠️ `SMTP_PASS` - Gmail 应用密码（16位，无连字符）
- ⚠️ `EMAIL_TO` - 收件邮箱（支持多个，逗号分隔）

### 可选配置（LLM 摘要）

- `HF_TOKEN` - Hugging Face Token（推荐，免费）
- `GITHUB_TOKEN` - GitHub Token（备选）
- `HF_MODEL_NAME` - 模型名称（可选，默认：Qwen/Qwen2.5-0.5B-Instruct）

如果不配置 LLM Token，系统会使用原始内容（不生成摘要）。

## 📋 上传前检查

1. ✅ 所有必需 Secrets 已配置
2. ✅ Secret 名称与代码中的环境变量名称匹配
3. ✅ Gmail 应用密码已获取（16位，无连字符）
4. ✅ 收件邮箱地址正确
5. ✅ 代码已提交到 GitHub 仓库

## 🚀 上传步骤

1. 提交所有代码到 GitHub
2. 在 GitHub 仓库页面，进入 **Settings** → **Secrets and variables** → **Actions**
3. 确认所有 Secrets 已配置
4. 进入 **Actions** 标签页
5. 点击 **Daily Global Intelligence Engine** workflow
6. 点击 **Run workflow** 手动触发测试
7. 查看运行日志，确认是否成功

## 🔍 常见问题

### Secret 名称说明
- 代码使用：`SMTP_PASS`（对应 Secret：`SMTP_PASS`）
- 代码使用：`EMAIL_TO`（对应 Secret：`EMAIL_TO`）

### 如何修改 Secret
1. 进入 **Settings** → **Secrets and variables** → **Actions**
2. 找到需要修改的 Secret
3. 点击右侧的 **Update** 按钮
4. 修改名称和值
5. 保存

## ✨ 测试建议

首次部署建议：
1. 先手动触发 workflow 测试
2. 检查日志输出
3. 确认邮件是否收到
4. 确认内容是否正确

如果一切正常，系统会在每天 UTC 23:00（北京时间早上 7:00）自动运行。

