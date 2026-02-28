"""
飞书推送模块
通过自定义机器人 Webhook 将日报摘要推送到飞书群聊
完整报告仍通过邮件发送；飞书仅推送标题 + 今日总结（若过长则截断，单次请求限制约 20KB）
"""
import re
from typing import Optional

import requests

from config import settings
from utils.logger import logger
from utils.time import get_today_date


# 飞书单次请求体建议不超过 20KB，正文保留约 4000 字符较安全
FEISHU_CONTENT_MAX_LEN = 4000


def _strip_html(html: str, max_len: int = 500) -> str:
    """去掉 HTML 标签并截断，用于无总结时的兜底文案。"""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:max_len] + "…") if len(text) > max_len else text


def send_report_to_feishu(
    html_content: str,
    report_summary: Optional[str] = None,
    title: Optional[str] = None,
) -> bool:
    """
    将日报摘要推送到飞书群（Webhook 自定义机器人）。

    Args:
        html_content: 完整 HTML 报告（本函数仅用于无 summary 时做兜底截断，不直接发送全文）
        report_summary: 今日总结与展望文案，优先使用
        title: 消息标题，默认带日期

    Returns:
        推送成功返回 True，未配置 Webhook 或推送失败返回 False（不影响邮件发送）
    """
    webhook = getattr(settings, "FEISHU_WEBHOOK_URL", None) or ""
    if not webhook or not webhook.startswith("http"):
        logger.debug("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送")
        return False

    if not title:
        title = f"全球科技与金融情报速览 - {get_today_date()}"

    # 正文：优先用 LLM 总结，否则用 HTML 截断兜底
    body = (report_summary or "").strip()
    if not body:
        body = _strip_html(html_content, max_len=FEISHU_CONTENT_MAX_LEN)
    if not body:
        body = "今日报告已生成，完整内容请查收邮件。"
    if len(body) > FEISHU_CONTENT_MAX_LEN:
        body = body[: FEISHU_CONTENT_MAX_LEN - 1].rstrip() + "…"

    # 飞书 post 富文本：title + 一段 content
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [
                        [{"tag": "text", "text": body}],
                    ],
                }
            }
        },
    }

    try:
        resp = requests.post(
            webhook,
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("StatusCode") == 0 or data.get("code") == 0:
                logger.info("飞书推送成功")
                return True
            logger.warning("飞书返回非成功: %s", data)
        else:
            logger.warning("飞书推送 HTTP %s: %s", resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        logger.warning("飞书推送请求异常: %s", e)
    except Exception as e:
        logger.warning("飞书推送失败: %s", e)
    return False
