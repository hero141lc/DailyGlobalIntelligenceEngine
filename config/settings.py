"""
配置管理模块
使用环境变量存储敏感信息
"""
import os
from typing import List, Dict

# 邮件配置（推荐使用 Gmail）
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")  # Gmail SMTP 服务器
SMTP_PORT_STR = os.getenv("SMTP_PORT", "587")  # Gmail SMTP 端口
try:
    SMTP_PORT = int(SMTP_PORT_STR) if SMTP_PORT_STR and SMTP_PORT_STR.strip() else 587
except (ValueError, TypeError):
    SMTP_PORT = 587  # 如果转换失败，使用默认值
SMTP_USER = os.getenv("SMTP_USER", "")  # Gmail 邮箱地址
SMTP_PASSWORD = os.getenv("SMTP_PASS", "")  # Gmail 应用密码（16位，无连字符）

# 收件邮箱配置（支持单个邮箱或列表）
# 方式1：单个邮箱 - "email@example.com"
# 方式2：多个邮箱（逗号分隔）- "email1@example.com,email2@example.com"
# 方式3：多个邮箱（JSON 数组）- '["email1@example.com","email2@example.com"]'
RECIPIENT_EMAIL_RAW = os.getenv("EMAIL_TO", "")
if RECIPIENT_EMAIL_RAW and RECIPIENT_EMAIL_RAW.strip():
    # 尝试解析为列表
    import json
    try:
        # 尝试解析为 JSON 数组
        RECIPIENT_EMAIL = json.loads(RECIPIENT_EMAIL_RAW)
        if not isinstance(RECIPIENT_EMAIL, list):
            RECIPIENT_EMAIL = [RECIPIENT_EMAIL] if RECIPIENT_EMAIL else []
        # 过滤空值
        RECIPIENT_EMAIL = [email.strip() for email in RECIPIENT_EMAIL if email and str(email).strip()]
    except (json.JSONDecodeError, ValueError, TypeError):
        # 如果不是 JSON，按逗号分隔
        RECIPIENT_EMAIL = [email.strip() for email in RECIPIENT_EMAIL_RAW.split(",") if email and email.strip()]
else:
    RECIPIENT_EMAIL = []

# LLM API 配置 - 使用 GitHub 提供的模型
# GitHub Actions 会自动提供 GITHUB_TOKEN 环境变量（通过 github.token）
# 也可以手动在 Secrets 中配置 GITHUB_TOKEN
# 如果 GITHUB_TOKEN 未设置，代码会尝试使用 github.token（在 GitHub Actions 环境中）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # GitHub Token
GITHUB_MODEL_NAME = os.getenv("GITHUB_MODEL_NAME", "gpt-4o-mini")  # GitHub 提供的模型名称

# 数据源配置
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.pussthecat.org",
    "https://nitter.privacyredirect.com",
]

# RSS 源配置
RSS_SOURCES: Dict[str, List[str]] = {
    "twitter_elon": [
        "https://rsshub.app/twitter/user/elonmusk",
    ],
    "twitter_trump": [
        "https://rsshub.app/twitter/user/realDonaldTrump",
    ],
    "energy": [
        "https://www.eia.gov/rss/todayinenergy.xml",
        "https://news.google.com/rss/search?q=energy+power+electricity+price&hl=en-US&gl=US&ceid=US:en",
    ],
    "ai": [
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "https://hnrss.org/frontpage",
    ],
    "space": [
        "https://news.google.com/rss/search?q=SpaceX+Starlink+launch&hl=en-US&gl=US&ceid=US:en",
    ],
    "fed": [
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://news.google.com/rss/search?q=Federal+Reserve+FOMC+interest+rate&hl=en-US&gl=US&ceid=US:en",
    ],
}

# 股票配置
# 注意：yfinance 在某些网络环境下可能无法访问，这是正常现象
STOCK_INDICES = {
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
}

# 大涨个股阈值（百分比）
STOCK_SURGE_THRESHOLD = 7.0

# LLM 配置
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 500
LLM_TEMPERATURE = 0.3

# 采集限制
MAX_TWEETS_PER_USER = 5
MAX_ITEMS_PER_SOURCE = 20

