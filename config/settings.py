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

# 飞书推送（可选）：配置 Webhook 后日报会推送到对应群聊
# 在飞书群组 → 设置 → 群机器人 → 添加自定义机器人 → 复制 Webhook 地址
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "").strip()

# 报告模式与推送通道（通用可配置架构）
# REPORT_MODE: daily_intel（全球日报）/ stock（股票情报）/ coal（煤炭情报）/ both（日报+煤炭同时运行）
REPORT_MODE = os.getenv("REPORT_MODE", "daily_intel").strip().lower() or "daily_intel"

# 推送通道默认值：全球日报/股票 → 邮件+飞书；煤炭 → 企业微信（可被环境变量覆盖）
PUSH_CHANNELS_RAW = os.getenv("PUSH_CHANNELS", "email,feishu").strip()  # daily_intel / stock 使用
PUSH_CHANNELS = [ch.strip().lower() for ch in PUSH_CHANNELS_RAW.split(",") if ch.strip()] or ["email", "feishu"]
COAL_PUSH_CHANNELS_RAW = os.getenv("COAL_PUSH_CHANNELS", "wecom").strip()  # coal 使用
COAL_PUSH_CHANNELS = [ch.strip().lower() for ch in COAL_PUSH_CHANNELS_RAW.split(",") if ch.strip()] or ["wecom"]

# 企业微信推送：仅群机器人 Webhook（推荐在 GitHub Secrets 配置 WECOM_WEBHOOK）
# 兼容两种写法：
# 1) WECOM_WEBHOOK: 完整 URL（推荐）
# 2) WECOM_KEY: 仅 key，代码会自动拼接为完整 URL
WECOM_WEBHOOK_RAW = os.getenv("WECOM_WEBHOOK", "").strip()
WECOM_KEY = os.getenv("WECOM_KEY", "").strip()
WECOM_WEBHOOK = (
    WECOM_WEBHOOK_RAW
    if WECOM_WEBHOOK_RAW and WECOM_WEBHOOK_RAW.startswith("http")
    else (f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WECOM_KEY}" if WECOM_KEY else "")
)

# 模式与数据源映射：每个模式启用哪些 source key（对应 SOURCE_MODULES 的 key）
MODE_SOURCES: Dict[str, List[str]] = {
    "daily_intel": [
        "web_sources", "google_rss", "energy", "commodities_military", "ai", "space",
        "fed", "stocks", "rss_extra", "twitter",
    ],
    "stock": ["stocks", "rss_extra", "fed"],
    "coal": ["coal_port", "coal_pit", "coal_powerplant", "coal_policy"],
}

# 煤炭数据源配置（REPORT_MODE=coal 时使用）
# 默认使用新浪财经 RSS（国内可访问），Google News 作为补充（海外/GitHub Actions 可用）
# 各源均为 RSS URL，支持环境变量覆盖；多条用逗号分隔
_COAL_PORT_DEFAULT = (
    "https://rss.sina.com.cn/finance/future.xml,"
    "https://news.google.com/rss/search?q=秦皇岛+动力煤+价格&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
)
_COAL_PIT_DEFAULT = (
    "https://rss.sina.com.cn/finance/future.xml,"
    "https://news.google.com/rss/search?q=榆林+鄂尔多斯+产地+坑口+煤价&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
)
_COAL_POWERPLANT_DEFAULT = (
    "https://rss.sina.com.cn/finance/future.xml,"
    "https://news.google.com/rss/search?q=电厂+库存+煤炭&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
)
_COAL_POLICY_DEFAULT = (
    "https://rss.sina.com.cn/roll/finance/hot_roll.xml,"
    "https://news.google.com/rss/search?q=中国+煤炭+政策&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
)

def _coal_sources(env_key: str, default: str) -> List[str]:
    raw = os.getenv(env_key, "").strip() or default
    return [u.strip() for u in raw.split(",") if u.strip()]

COAL_PORT_SOURCES: List[str] = _coal_sources("COAL_PORT_URL", _COAL_PORT_DEFAULT)
COAL_PIT_SOURCES: List[str] = _coal_sources("COAL_PIT_URL", _COAL_PIT_DEFAULT)
COAL_POWERPLANT_SOURCES: List[str] = _coal_sources("COAL_POWERPLANT_URL", _COAL_POWERPLANT_DEFAULT)
COAL_POLICY_SOURCES: List[str] = _coal_sources("COAL_POLICY_URL", _COAL_POLICY_DEFAULT)

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
    # 知名企业：维谛技术、美光、甲骨文、七姐妹等财报/订单/技术/CEO 访华
    "corporate": [
        "https://news.google.com/rss/search?q=Vertiv+earnings+order&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Micron+Oracle+earnings+revenue&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Big+Oil+CEO+China+visit+Exxon+Chevron&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=tech+giant+earnings+forecast+quarterly&hl=en-US&gl=US&ceid=US:en",
    ],
    # 关键人物：黄仁勋、英特尔、谷歌等官媒/实时
    "key_figures": [
        "https://news.google.com/rss/search?q=Jensen+Huang+NVIDIA&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Intel+CEO+Pat+Gelsinger&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Google+Alphabet+Sundar+Pichai&hl=en-US&gl=US&ceid=US:en",
    ],
    # 地缘政治
    "geopolitics": [
        "https://news.google.com/rss/search?q=US+China+geopolitics+trade&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=Russia+Ukraine+NATO+sanctions&hl=en-US&gl=US&ceid=US:en",
    ],
    # 美国专业机构/量化/研报
    "institutional": [
        "https://news.google.com/rss/search?q=institutional+investor+quant+hedge+fund&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=research+report+analyst+rating+stock&hl=en-US&gl=US&ceid=US:en",
    ],
}

# 股票配置（Stooq 格式）
STOCK_INDICES = {
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
    "纳指100": "^NDX",  # 纳斯达克 100
    "费城半导体": "^SOX",  # 半导体指数
}
# 重点关注个股：七姐妹(油)、维谛/美光/甲骨文/半导体/生物医药/消费/工业等
STOCK_WATCHLIST = [
    # 科技与七姐妹
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "VRT", "MU", "ORCL", "INTC", "AMD", "CRM", "ADBE", "NFLX",
    # 半导体与硬件
    "AVGO", "QCOM", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL", "ARM", "SMCI",
    # 软件与云/安全
    "PANW", "CRWD", "SNOW", "DDOG", "NET", "NOW", "INTU",
    # 能源（七姐妹 + 油服）
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "OXY", "DVN", "HAL",
    # 金融
    "JPM", "BAC", "GS", "MS", "C", "SCHW", "AXP", "BLK",
    # 消费与零售
    "WMT", "COST", "TGT", "HD", "NKE", "SBUX", "MCD", "DIS",
    # 医药与生物科技
    "JNJ", "UNH", "LLY", "ABBV", "MRK", "PFE", "BMY", "REGN", "VRTX", "MRNA",
    # 工业与军工
    "CAT", "DE", "LMT", "RTX", "HON", "GE", "UPS", "BA",
    # 其他大盘
    "BRK-B", "V", "MA", "PG", "IBM", "CSCO", "TXN",
]

# 大涨个股阈值（百分比）
STOCK_SURGE_THRESHOLD = 7.0

# 今日涨跌一览：取涨跌幅前 N 的个股（无论是否≥大涨阈值），丰富股票板块
STOCK_DAILY_MOVERS_TOP = 12
# Stooq 每次请求间隔（秒），避免 GitHub Actions 等环境被限流导致只返回少量股票
STOOQ_DELAY = 0.5

# LLM 配置（扩大 token 以支持更长摘要与总结）
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 4000
LLM_TEMPERATURE = 0.3

# 采集限制
MAX_TWEETS_PER_USER = 5
MAX_ITEMS_PER_SOURCE = 20

# Google News RSS 统一函数：预设与任务（独立线程，每次请求间隔 1 秒）
# 预设：全球中文 24h / 全球英文 24h / 按话题（topic 需配合 topic_keywords）
GOOGLE_NEWS_PRESETS: Dict[str, Dict[str, str]] = {
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
}
# 任务列表：仅英文信源（中文为二手数据不采集）；每项 preset, topic_keywords(可选), category, max_items(可选)
GOOGLE_NEWS_TASKS: List[Dict] = [
    {"preset": "en", "category": "世界新闻", "keywords_filter": []},
    # 产业链与涨价（MLCC/被动元件/券商纪要式信息，重要前置）
    {"preset": "topic", "topic_keywords": ["MLCC", "capacitor", "price increase", "Murata", "Yageo", "passive component"], "category": "产业链与涨价", "max_items": 10},
    # 商业航天产业链（发动机、抗干扰芯片等）
    {"preset": "topic", "topic_keywords": ["rocket engine", "commercial space", "Starlink", "antenna", "chip"], "category": "商业航天产业链", "max_items": 10},
    # 机器人产业链（伺服、丝杠、人形机器人）
    {"preset": "topic", "topic_keywords": ["servo", "ball screw", "humanoid robot", "harmonic drive"], "category": "机器人产业链", "max_items": 10},
    # 国内科技/华为（华为、小米、比亚迪、中兴、荣耀等，与国外大厂并列）
    {"preset": "topic", "topic_keywords": ["Huawei", "China tech", "HarmonyOS", "Xiaomi", "BYD", "ZTE", "Honor"], "category": "国内科技/华为", "max_items": 12},
    # 国内AI应用（与国外 AI 应用板块对应）
    {"preset": "topic", "topic_keywords": ["China AI", "Baidu AI", "Alibaba AI", "Tencent AI", "Chinese AI", "Kimi", "DeepSeek"], "category": "国内AI应用", "max_items": 10},
    # 国内商业航天（与国外商业航天对应：长征、星河动力、星际荣耀、蓝箭等）
    {"preset": "topic", "topic_keywords": ["China commercial space", "CASC", "Galactic Energy", "LandSpace", "i-Space", "Chinese rocket", "Long March"], "category": "国内商业航天", "max_items": 10},
    # 英伟达/特斯拉/谷歌与国内订单
    {"preset": "topic", "topic_keywords": ["NVIDIA", "order", "Tesla", "order", "Google", "order", "China", "domestic order"], "category": "大厂与国内订单", "max_items": 12},
    # 储能订单
    {"preset": "topic", "topic_keywords": ["energy storage", "BESS", "storage order", "storage tender"], "category": "储能订单", "max_items": 10},
    # 太空光伏
    {"preset": "topic", "topic_keywords": ["space solar", "SPS", "orbital solar", "space-based solar"], "category": "太空光伏", "max_items": 8},
    # 原有任务
    {"preset": "topic", "topic_keywords": ["Vertiv", "Micron", "Oracle", "earnings"], "category": "知名企业/财报", "max_items": 15},
    {"preset": "topic", "topic_keywords": ["Big Oil", "CEO", "China", "visit"], "category": "知名企业/财报", "max_items": 10},
    {"preset": "topic", "topic_keywords": ["Jensen Huang", "NVIDIA"], "category": "关键人物", "max_items": 10},
    {"preset": "topic", "topic_keywords": ["Intel", "Google", "Alphabet"], "category": "关键人物", "max_items": 10},
    {"preset": "topic", "topic_keywords": ["geopolitics", "US", "China"], "category": "地缘政治", "max_items": 12},
    {"preset": "topic", "topic_keywords": ["institutional", "quant", "research", "report"], "category": "机构研报", "max_items": 10},
]
GOOGLE_NEWS_REQUEST_INTERVAL = 1  # 秒

# 日报总结：使用 DeepSeek-R1 带思考，单次请求控制在约 4000 token（输入+输出）
# GitHub Models 中模型名为 openai/gpt-4.1-mini
REPORT_SUMMARY_MODEL = os.getenv("REPORT_SUMMARY_MODEL", "gpt-4.1-mini")
REPORT_SUMMARY_MAX_INPUT_ITEMS = 35
REPORT_SUMMARY_MAX_TOKENS = 4000
REPORT_SUMMARY_MAX_INPUT_CHARS_PER_ITEM = 80

