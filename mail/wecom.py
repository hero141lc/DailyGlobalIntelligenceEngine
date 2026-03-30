"""
企业微信推送模块
仅支持：企业微信群机器人 Webhook
"""

import requests

from utils.logger import logger

# 群机器人 Markdown 建议不超过 4096 字节
WECOM_MARKDOWN_MAX_LEN = 4096


def _truncate_content(text: str, max_len: int = WECOM_MARKDOWN_MAX_LEN) -> str:
    text = (text or "").strip()
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "…"
    return text


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
    text = _truncate_content(content)
    if not text:
        logger.warning("企业微信推送内容为空，跳过")
        return {"errcode": -1, "errmsg": "content empty"}
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
        if data.get("errcode") == 0:
            logger.info("企业微信推送成功")
        else:
            logger.warning("企业微信返回非成功: %s", data)
        return data
    except requests.RequestException as e:
        logger.warning("企业微信推送请求异常: %s", e)
        return {"errcode": -1, "errmsg": str(e)}
    except Exception as e:
        logger.warning("企业微信推送失败: %s", e)
        return {"errcode": -1, "errmsg": str(e)}
