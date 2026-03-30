"""
企业微信推送模块
仅支持：企业微信群机器人 Webhook
"""

import requests

from utils.logger import logger

# 群机器人 Markdown 最大 4096 字节（UTF-8）
WECOM_MARKDOWN_MAX_BYTES = 4096


def _split_markdown_content(text: str, max_bytes: int = WECOM_MARKDOWN_MAX_BYTES) -> list[str]:
    """
    按 UTF-8 字节长度切分 Markdown 内容，确保每段 <= max_bytes。
    优先按换行分段，避免破坏可读性；若单行超长则按字符硬切。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    chunks: list[str] = []
    current = ""

    def _utf8_len(s: str) -> int:
        return len(s.encode("utf-8"))

    lines = raw.splitlines(keepends=True)
    for line in lines:
        # 当前行本身已超限，先落盘 current，再把该行硬切
        if _utf8_len(line) > max_bytes:
            if current:
                chunks.append(current.rstrip())
                current = ""
            buf = ""
            for ch in line:
                if _utf8_len(buf + ch) > max_bytes:
                    chunks.append(buf.rstrip())
                    buf = ch
                else:
                    buf += ch
            if buf:
                chunks.append(buf.rstrip())
            continue

        if not current:
            current = line
            continue

        if _utf8_len(current + line) <= max_bytes:
            current += line
        else:
            chunks.append(current.rstrip())
            current = line

    if current:
        chunks.append(current.rstrip())
    return [c for c in chunks if c]


def send_wecom(content: str, webhook: str = "") -> dict:
    """
    统一入口：仅群机器人 Webhook。
    参数可从 config.settings 传入，不传则内部读取 WECOM_WEBHOOK。
    """
    from config import settings
    wh = webhook or getattr(settings, "WECOM_WEBHOOK", "") or ""
    if wh and str(wh).startswith("http"):
        return send_wecom_message(wh, content)
    logger.warning("企业微信未配置（需 WECOM_WEBHOOK 或 WECOM_KEY），跳过推送")
    return {"errcode": -1, "errmsg": "not configured"}


def send_wecom_message(webhook: str, content: str) -> dict:
    """群机器人 Webhook 方式发送 Markdown 消息。"""
    if not webhook or not str(webhook).strip().startswith("http"):
        logger.warning("WECOM_WEBHOOK 未配置或无效，跳过企业微信推送")
        return {"errcode": -1, "errmsg": "webhook not configured"}
    chunks = _split_markdown_content(content)
    if not chunks:
        logger.warning("企业微信推送内容为空，跳过")
        return {"errcode": -1, "errmsg": "content empty"}

    logger.info("企业微信消息分片发送：共 %d 条", len(chunks))
    for idx, text in enumerate(chunks, start=1):
        payload = {"msgtype": "markdown", "markdown": {"content": text}}
        try:
            resp = requests.post(
                webhook,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                logger.warning("企业微信第 %d 条发送失败: %s", idx, data)
                return data
            logger.info("企业微信第 %d/%d 条发送成功", idx, len(chunks))
        except requests.RequestException as e:
            logger.warning("企业微信第 %d 条请求异常: %s", idx, e)
            return {"errcode": -1, "errmsg": str(e)}
        except Exception as e:
            logger.warning("企业微信第 %d 条发送失败: %s", idx, e)
            return {"errcode": -1, "errmsg": str(e)}
    return {"errcode": 0, "errmsg": "ok"}
