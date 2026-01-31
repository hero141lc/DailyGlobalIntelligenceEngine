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
# 🔥 关键：必须在 workflow 中设置 permissions.models: read 才能访问 GitHub Models
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # GitHub Token
GITHUB_MODEL_NAME = os.getenv("GITHUB_MODEL_NAME", "gpt-4o-mini")  # GitHub 提供的模型名称

# 数据源配置（Nitter 已禁用：均为 404，马斯克/特朗普改由 WEB_SOURCES 网页采集）
NITTER_INSTANCES: List[str] = []

# 网页消息来源（非 RSS，仿真请求头 + 独立线程；与 RSS 的 twitter_elon/twitter_trump 并存）
WEB_SOURCES: Dict[str, List[str]] = {
    "twitter_elon": [
        "https://xcancel.com/elonmusk/with_replies",
    ],
    # 特朗普：Truth Social 归档 JSON（与 RSS 并存；Nitter 在 Actions 中 403 已弃用）
    "twitter_trump": [
        "https://stilesdata.com/trump-truth-social-archive/truth_archive.json",
    ],
}
# 备忘 Elon: xcancel；Trump: stilesdata Truth Social JSON + RSS（Google News）

# 网页请求仿真头（模拟浏览器）
WEB_REQUEST_HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

WEB_REQUEST_INTERVAL = 1  # 秒（网页来源请求间隔）
WEB_REQUEST_RETRIES = 5   # 网页来源（推特/智能网关）请求失败时默认重试次数

# RSS 源配置：每类多源，顺序尝试，一个不行就用下一个
RSS_SOURCES: Dict[str, List[str]] = {
    # 能源（政府/行业站优先，再 Google）
    "energy": [
        "https://www.eia.gov/rss/todayinenergy.xml",
        "https://oilprice.com/rss/main",
        "https://www.rigzone.com/news/rss/",
        "https://world-nuclear-news.org/?rss=feed",
        "https://news.google.com/rss/search?q=energy+power+electricity+price&hl=en-US&gl=US&ceid=US:en",
    ],
    # 科技与 AI（多站 + HN）
    "ai": [
        "https://techcrunch.com/tag/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.wired.com/feed/rss",
        "https://www.theverge.com/rss/index.xml",
        "https://arstechnica.com/feed/",
        "https://hnrss.org/frontpage?points=100",
    ],
    # 商业航天（spacenews 易限流，放最后）
    "space": [
        "https://www.space.com/feeds/all",
        "https://www.nasaspaceflight.com/feed/",
        "https://news.google.com/rss/search?q=SpaceX+Starlink+launch&hl=en-US&gl=US&ceid=US:en",
        "https://spacenews.com/feed/",
    ],
    # 美联储/宏观（官方 + 财经站 + Google）
    "fed": [
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.investing.com/rss/news_285.rss",
        "https://news.google.com/rss/search?q=Federal+Reserve+FOMC+interest+rate&hl=en-US&gl=US&ceid=US:en",
    ],
    # 黄金（bullionvault RSS 已 400，仅保留 mining + Google）
    "gold": [
        "https://www.mining.com/feed/",
        "https://news.google.com/rss/search?q=gold+price+precious+metal&hl=en-US&gl=US&ceid=US:en",
    ],
    # 石油（行业站 + Google）
    "oil": [
        "https://oilprice.com/rss/main",
        "https://www.rigzone.com/news/rss/",
        "https://news.google.com/rss/search?q=oil+crude+WTI+Brent&hl=en-US&gl=US&ceid=US:en",
    ],
    # 军事（多站 + Google；避免 Reuters 在 Actions 中 DNS 不可达）
    "military": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.defenseone.com/rss/all",
        "https://news.google.com/rss/search?q=military+defense+Pentagon+Ukraine&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Ukraine+NATO+army+defense+war&hl=en-US&gl=US&ceid=US:en",
    ],
    # 美股快讯（多财经站，一个不行用下一个）
    "stocks": [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "http://feeds.marketwatch.com/marketwatch/topstories/",
        "https://seekingalpha.com/market_currents.xml",
        "https://finance.yahoo.com/rss/topstories",
        "https://news.google.com/rss/search?q=stock+market+US+NYSE+NASDAQ&hl=en-US&gl=US&ceid=US:en",
    ],
    # SEC 监管（特斯拉等，可再加其他 CIK）
    "sec_filings": [
        "https://data.sec.gov/rss?cik=1318605&type=&exclude=true&count=40",
    ],
    # 马斯克/特朗普：Google News RSS（与 WEB_SOURCES 网页抓取并存）
    "twitter_elon": [
        "https://news.google.com/rss/search?q=from:elonmusk+site:x.com&hl=en-US&gl=US&ceid=US:en",
    ],
    "twitter_trump": [
        "https://news.google.com/rss/search?q=from:realDonaldTrump+site:x.com&hl=en-US&gl=US&ceid=US:en",
    ],
}

# 股票配置（Stooq 格式）
STOCK_INDICES = {
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
}

# 大涨个股阈值（百分比）
STOCK_SURGE_THRESHOLD = 7.0

# 今日涨跌一览：取涨跌幅前 N 的个股（无论是否≥大涨阈值），丰富股票板块
STOCK_DAILY_MOVERS_TOP = 5

# LLM 配置（扩大 token 以支持更长摘要与总结）
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 12000
LLM_TEMPERATURE = 0.3

# 采集限制
MAX_TWEETS_PER_USER = 5
MAX_ITEMS_PER_SOURCE = 20

