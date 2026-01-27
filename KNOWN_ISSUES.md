# 已知问题和解决方案

## 1. 邮件配置问题

**症状**：日志显示"未配置邮件账户信息"

**可能原因**：
- GitHub Secrets 名称不匹配
- Secrets 值为空
- 环境变量未正确传递

**解决方案**：
1. 检查 GitHub Secrets 配置：
   - `SMTP_USER` - 必须配置
   - `SMTP_PASS` - 必须配置（不是 `SMTP_PASSWORD`）
   - `EMAIL_TO` - 必须配置
2. 确认 Secrets 值不为空
3. 重新运行 workflow

## 2. Hugging Face API 410 Gone 错误

**症状**：摘要生成失败，返回 410 Client Error: Gone

**原因**：模型端点不存在或已移除

**解决方案**：
1. 在 GitHub Secrets 中配置 `HF_MODEL_NAME` 为其他可用模型
2. 推荐模型：
   - `microsoft/DialoGPT-medium`
   - `gpt2`（英文模型）
   - 或访问 https://huggingface.co/models 查找可用的中文模型
3. 如果不配置 LLM Token，系统会使用原始内容（不生成摘要）

## 3. 网络连接问题

**症状**：多个 RSS 源无法访问（DNS 解析失败）

**原因**：GitHub Actions 的网络限制，某些域名可能被阻止

**解决方案**：
- 这是正常现象，代码已处理
- 单个数据源失败不会影响整体运行
- 系统会继续尝试其他数据源

## 4. yfinance 股票数据获取失败

**症状**：所有股票数据获取失败，显示 "Expecting value: line 1 column 1"

**原因**：
- yfinance API 限制
- 网络连接问题
- API 端点变更

**解决方案**：
- 这是正常现象，代码已处理
- 股票数据获取失败不会影响其他数据采集
- 系统会继续运行并发送其他数据

## 5. 时区警告

**症状**：`UnknownTimezoneWarning: tzname EST identified but not understood`

**原因**：dateutil 解析时区时的警告

**解决方案**：
- 这是警告，不影响功能
- 可以忽略

## 建议配置

### 最小配置（必需）
- `SMTP_USER` - Gmail 邮箱
- `SMTP_PASS` - Gmail 应用密码
- `EMAIL_TO` - 收件邮箱

### 可选配置
- `HF_TOKEN` - Hugging Face Token（用于摘要生成）
- `HF_MODEL_NAME` - 模型名称（如果默认模型不可用）

### 不配置也可以
- `SMTP_HOST` - 默认 `smtp.gmail.com`
- `SMTP_PORT` - 默认 `587`
- LLM 相关配置 - 不配置会使用原始内容

