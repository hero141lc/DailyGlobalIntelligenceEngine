"""
配置管理模块
使用环境变量存储敏感信息
"""
import os
from typing import List, Dict

# 邮件配置（推荐使用 Gmail）
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")  # Gmail SMTP 服务器
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))  # Gmail SMTP 端口
SMTP_USER = os.getenv("SMTP_USER", "")  # Gmail 邮箱地址
SMTP_PASSWORD = os.getenv("SMTP_PASS", "")  # Gmail 应用密码（16位，无连字符）

# 收件邮箱配置（支持单个邮箱或列表）
# 方式1：单个邮箱 - "email@example.com"
# 方式2：多个邮箱（逗号分隔）- "email1@example.com,email2@example.com"
# 方式3：多个邮箱（JSON 数组）- '["email1@example.com","email2@example.com"]'
RECIPIENT_EMAIL_RAW = os.getenv("EMAIL_TO", "")
if RECIPIENT_EMAIL_RAW:
    # 尝试解析为列表
    import json
    try:
        # 尝试解析为 JSON 数组
        RECIPIENT_EMAIL = json.loads(RECIPIENT_EMAIL_RAW)
        if not isinstance(RECIPIENT_EMAIL, list):
            RECIPIENT_EMAIL = [RECIPIENT_EMAIL]
    except (json.JSONDecodeError, ValueError):
        # 如果不是 JSON，按逗号分隔
        RECIPIENT_EMAIL = [email.strip() for email in RECIPIENT_EMAIL_RAW.split(",") if email.strip()]
else:
    RECIPIENT_EMAIL = []

# LLM API 配置
# 支持使用 GitHub Token 或 Hugging Face Token 访问免费模型
# 优先使用 HF_TOKEN，如果没有则使用 GITHUB_TOKEN
HF_TOKEN = os.getenv("HF_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODELS_API_KEY = HF_TOKEN or GITHUB_TOKEN  # 自动选择可用的 token
# 如果使用 GitHub Token，需要先在 Hugging Face 设置中关联 GitHub 账号
# 或者直接使用 Hugging Face Token（推荐）
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")  # 免费中文模型

# OpenAI API 配置（备选，需付费）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 数据源配置
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.pussthecat.org",
    "https://nitter.privacyredirect.com",
]

# RSS 源配置
RSS_SOURCES: Dict[str, List[str]] = {
    "twitter_elon": [
        "https://nitter.net/elonmusk/rss",
        "https://nitter.pussthecat.org/elonmusk/rss",
    ],
    "twitter_trump": [
        "https://nitter.net/realDonaldTrump/rss",
        "https://nitter.pussthecat.org/realDonaldTrump/rss",
    ],
    "energy": [
        "https://www.eia.gov/rss/todayinenergy.xml",
        "https://feeds.reuters.com/reuters/energy",
    ],
    "ai": [
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "https://hnrss.org/frontpage",
    ],
    "space": [
        "https://spacenews.com/feed/",
        "https://feeds.reuters.com/reuters/aerospace",
    ],
    "fed": [
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
}

# 股票配置
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

