"""
LLM 摘要模块
使用 GitHub 提供的模型 API（通过 models.inference.ai.azure.com）
"""
import re
import requests
import time
from typing import List, Dict, Optional

from config import settings
from utils.logger import logger

def summarize_with_github_models(item: Dict, max_retries: int = 3) -> Optional[str]:
    """
    使用 GitHub Models API 生成中文摘要
    
    Args:
        item: 数据项字典
        max_retries: 最大重试次数
    
    Returns:
        中文摘要，失败返回 None
    """
    github_token = settings.GITHUB_TOKEN
    if not github_token:
        logger.warning("未配置 GITHUB_TOKEN，跳过摘要生成，使用原始内容")
        return None
    
    # 验证 token 格式（应该是非空字符串）
    if not isinstance(github_token, str) or len(github_token.strip()) == 0:
        logger.warning("GITHUB_TOKEN 格式无效，跳过摘要生成")
        return None
    
    # GitHub Models API 端点（通过 Azure 提供）
    url = "https://models.inference.ai.azure.com/chat/completions"
    
    # 构建 prompt
    prompt = f"""你是一位专业的投资情报分析师。请将以下英文信息总结成简洁的中文摘要，要求：

1. 输出语言：中文
2. 风格：投资情报/晨报风格，客观、简洁
3. 只总结原始信息，不要猜测或扩展
4. 保持关键事实和数据
5. 长度控制在 100 字以内

原始信息：
标题：{item.get('title', '')}
内容：{item.get('content', '')}
来源：{item.get('source', '')}

请直接输出中文摘要，不要包含任何其他说明："""
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": settings.GITHUB_MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一位专业的投资情报分析师，擅长将英文信息总结成简洁的中文摘要。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            # 检查 401 错误（认证失败）
            if response.status_code == 401:
                logger.error(f"GitHub Models API 认证失败（401）：请检查 GITHUB_TOKEN 是否正确，并确保 workflow 中设置了 permissions.models: read")
                return None
            # 检查 400 错误（请求体/参数不合法，如 token 超限）
            if response.status_code == 400:
                try:
                    err_body = (response.text or "")[:300]
                    logger.warning(f"GitHub Models API 请求错误（400）: {err_body}")
                except Exception:
                    logger.warning("GitHub Models API 请求错误（400）")
                return None
            
            # 检查 429 错误（限流）
            if response.status_code == 429:
                # 429 错误需要等待更长时间
                # 尝试1: 15秒, 尝试2: 20秒, 尝试3: 25秒
                wait_time = 15 + (5 * attempt)  # 基础15秒 + 每次增加5秒
                logger.warning(f"GitHub Models API 限流（429），等待 {wait_time} 秒后重试（尝试 {attempt + 1}/{max_retries}）")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue  # 直接重试，不抛出异常
                else:
                    logger.error(f"摘要生成最终失败（限流）: {item.get('title', '')}")
                    logger.warning("提示：GitHub Models 免费版有速率限制，建议减少并发请求或增加延迟时间")
                    return None
            
            response.raise_for_status()
            result = response.json()
            
            # 解析响应（OpenAI 兼容格式）
            summary = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if summary:
                logger.debug(f"摘要生成成功（模型：{settings.GITHUB_MODEL_NAME}）")
                return summary
            else:
                logger.warning(f"摘要生成返回空结果: {item.get('title', '')}")
                return None
                
        except requests.exceptions.RequestException as e:
            # 401 和 429 错误已经在上面处理，这里处理其他 HTTP 错误
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 401:
                    logger.error(f"GitHub Models API 认证失败（401）：请检查 GITHUB_TOKEN 和 workflow permissions")
                    return None
                if status_code == 429:
                    # 429 错误已经在上面处理，这里不应该到达
                    wait_time = 10 + (2 ** attempt)
                    logger.warning(f"GitHub Models API 限流（429），等待 {wait_time} 秒后重试")
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"摘要生成最终失败（限流）: {item.get('title', '')}")
                        return None
                logger.warning(f"摘要生成失败（HTTP {status_code}，尝试 {attempt + 1}/{max_retries}）: {e}")
            else:
                logger.warning(f"摘要生成失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                logger.error(f"摘要生成最终失败: {item.get('title', '')}")
                return None
        except Exception as e:
            logger.error(f"摘要生成异常: {e}")
            return None
    
    return None

def summarize_item(item: Dict) -> Dict:
    """
    为单个数据项生成摘要
    
    Args:
        item: 数据项字典
    
    Returns:
        添加了 summary 字段的数据项字典
    """
    # 使用 GitHub Models API
    summary = summarize_with_github_models(item)
    
    # 如果摘要生成失败，使用原始内容的前200字
    if not summary:
        original_content = item.get("content", item.get("title", ""))
        summary = original_content[:200] + ("..." if len(original_content) > 200 else "")
    
    item["summary"] = summary
    return item

def summarize_batch(items: List[Dict], delay: float = 1.2) -> List[Dict]:
    """
    批量生成摘要（逐条调用，保留用于回退）
    """
    summarized_items: List[Dict] = []
    for i, item in enumerate(items):
        logger.info(f"生成摘要 {i + 1}/{len(items)}: {item.get('title', '')[:50]}")
        summarized_item = summarize_item(item)
        summarized_items.append(summarized_item)
        if i < len(items) - 1:
            time.sleep(delay)
    return summarized_items


def _call_github_models(
    messages: List[Dict],
    max_tokens: int = None,
    max_retries: int = 3,
    model: str = None,
    extra_body: Optional[Dict] = None,
) -> Optional[str]:
    """调用 GitHub Models API，返回 content 文本。"""
    github_token = settings.GITHUB_TOKEN
    if not github_token or not isinstance(github_token, str) or not github_token.strip():
        return None
    url = "https://models.inference.ai.azure.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model or settings.GITHUB_MODEL_NAME,
        "messages": messages,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
    }
    if extra_body:
        data.update(extra_body)
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 401:
                logger.error("GitHub Models API 认证失败（401）")
                return None
            if response.status_code == 400:
                try:
                    err_body = response.text[:500] if response.text else "无响应体"
                    logger.warning(f"GitHub Models API 请求错误（400），可能为输入/输出 token 超限或参数不合法: {err_body}")
                except Exception:
                    logger.warning("GitHub Models API 请求错误（400）")
                return None
            if response.status_code == 429:
                wait_time = 15 + (5 * attempt)
                logger.warning(f"API 限流（429），{wait_time}s 后重试（{attempt + 1}/{max_retries}）")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
                return None
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return content if content else None
        except Exception as e:
            logger.warning(f"API 调用失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None  # 所有重试后仍未返回则返回 None


def _call_github_models_with_reasoning(
    messages: List[Dict],
    max_tokens: int,
    model: str,
    max_retries: int = 3,
) -> Dict[str, str]:
    """调用 DeepSeek-R1 等带思考的模型，返回 {"summary": content, "reasoning": reasoning_content}。"""
    github_token = settings.GITHUB_TOKEN
    out = {"summary": "", "reasoning": ""}
    if not github_token or not isinstance(github_token, str) or not github_token.strip():
        return out
    url = "https://models.inference.ai.azure.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    # 部分推理模型通过 extra_body 启用 thinking
    extra = getattr(settings, "REPORT_SUMMARY_EXTRA_BODY", None)
    if extra:
        data.update(extra)
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 401:
                logger.error("GitHub Models API 认证失败（401）")
                return out
            if response.status_code == 400:
                try:
                    err_body = (response.text or "")[:500]
                    logger.warning(f"日报总结 API 请求错误（400）: {err_body}")
                except Exception:
                    pass
                return out
            if response.status_code == 429:
                wait_time = 15 + (5 * attempt)
                logger.warning(f"API 限流（429），{wait_time}s 后重试")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
                return out
            response.raise_for_status()
            result = response.json()
            msg = result.get("choices", [{}])[0].get("message", {})
            out["summary"] = (msg.get("content") or "").strip()
            out["reasoning"] = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
            return out
        except Exception as e:
            logger.warning(f"日报总结 API 调用失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return out


# 每批最多条目数，避免单次请求 token 超限导致 400
BATCH_CHUNK_SIZE = 25

def _summarize_one_chunk(chunk: List[Dict], start_index: int) -> List[Optional[str]]:
    """对一小批条目调用 API 生成摘要，返回与 chunk 等长的摘要列表。"""
    n = len(chunk)
    lines = []
    for i, item in enumerate(chunk, 1):
        title = (item.get("title") or "")[:120]
        content = (item.get("content") or item.get("title") or "")[:200]
        content = content.replace("\n", " ").strip()
        lines.append(f"[{i}] 标题：{title}\n    内容：{content}")
    block = "\n\n".join(lines)
    prompt = f"""你是一位专业的投资情报分析师。请将以下 {n} 条英文信息分别总结成简洁的中文摘要。

要求：
1. 输出语言：中文
2. 风格：投资情报/晨报风格，客观、简洁
3. 只总结原始信息，不要猜测或扩展
4. 每条摘要控制在 80 字以内
5. 必须严格按顺序输出，格式为每行一条：
1. 第一条的中文摘要
2. 第二条的中文摘要
...
{n}. 第{n}条的中文摘要

原始信息（每条以 [序号] 开头）：
{block}

请直接输出 {n} 条摘要，不要其他说明："""
    messages = [
        {"role": "system", "content": "你擅长将英文情报总结成简洁的中文摘要，并严格按序号逐条输出。"},
        {"role": "user", "content": prompt},
    ]
    cap = getattr(settings, "LLM_MAX_TOKENS", 2000) or 2000
    batch_max = min(4096, max(800, 150 * n + 200))  # 单批输出上限，避免超模型 context
    raw = _call_github_models(messages, max_tokens=batch_max)
    if not raw:
        return [None] * n
    summaries = [None] * n
    for j, ln in enumerate([ln.strip() for ln in raw.split("\n") if ln.strip()]):
        if j >= n:
            break
        t = re.sub(r"^\d+[\.．)\s]+", "", ln).strip()
        if t and len(t) > 2:
            summaries[j] = t[:300]
    if sum(1 for s in summaries if s) < n:
        for i in range(1, n + 1):
            if summaries[i - 1]:
                continue
            pat = re.compile(rf"^{i}[\.．)\s]+\s*(.+?)(?=\n\d+[\.．)\s]+|\Z)", re.DOTALL | re.MULTILINE)
            m = pat.search(raw)
            if m:
                s = m.group(1).strip().replace("\n", " ").strip()
                if s:
                    summaries[i - 1] = s[:300]
    return summaries


def summarize_batch_unified(items: List[Dict]) -> List[Dict]:
    """
    分批为所有条目生成中文简介（每批 BATCH_CHUNK_SIZE 条一次调用），避免单次请求过大导致 400。
    要求模型按顺序输出「1. 摘要\\n2. 摘要\\n...」，解析后写回各条目的 summary。
    """
    if not items:
        return items
    chunk_size = BATCH_CHUNK_SIZE
    all_summaries = [None] * len(items)
    for start in range(0, len(items), chunk_size):
        chunk = items[start : start + chunk_size]
        chunk_summaries = _summarize_one_chunk(chunk, start)
        for k, s in enumerate(chunk_summaries):
            if start + k < len(all_summaries):
                all_summaries[start + k] = s
        if start + chunk_size < len(items):
            time.sleep(2)  # 批与批之间间隔，减轻 429
    failed = sum(1 for s in all_summaries if not s)
    if failed == len(items):
        logger.warning("统一摘要 API 未返回内容，回退为逐条摘要或截断原文")
        return summarize_batch(items, delay=1.5)
    for idx, item in enumerate(items):
        s = all_summaries[idx] if idx < len(all_summaries) and all_summaries[idx] else None
        if not s:
            orig = item.get("content", item.get("title", ""))
            s = orig[:200] + ("..." if len(orig) > 200 else "")
        item["summary"] = s
    logger.info(f"统一摘要完成：{len(items)} 条")
    return items


def generate_report_summary_with_reasoning(items: List[Dict]) -> Dict[str, str]:
    """
    使用 DeepSeek-R1 等带思考模型生成日报总结，单次请求控制在约 4000 token（输入+输出）。
    返回 {"summary": 正文, "reasoning": 思考过程}，思考在报告中默认折叠展示。
    """
    out = {"summary": "", "reasoning": ""}
    if not items:
        return out
    max_items = getattr(settings, "REPORT_SUMMARY_MAX_INPUT_ITEMS", 35) or 35
    max_chars = getattr(settings, "REPORT_SUMMARY_MAX_INPUT_CHARS_PER_ITEM", 80) or 80
    max_tokens = getattr(settings, "REPORT_SUMMARY_MAX_TOKENS", 2000) or 2000
    model = getattr(settings, "REPORT_SUMMARY_MODEL", "deepseek-reasoner") or "deepseek-reasoner"

    parts = []
    for i, item in enumerate(items[:max_items], 1):
        title = (item.get("title") or "")[:max_chars]
        summary = item.get("summary") or item.get("content") or ""
        summary = (summary[:max_chars] if summary else "").replace("\n", " ")
        cat = item.get("category", "")
        parts.append(f"[{i}] [{cat}] {title} | {summary}")
    block = "\n".join(parts)

    prompt = f"""你是一位全球科技与金融情报分析师。根据以下今日情报条目，写一长段「今日总结与展望」，要求深度分析、信息密度高。

要求：
1. 中文，整体为一长串连贯段落（不要分小节标题，不要列表符号）。
2. 总结部分（前半）：对今日情报做深度分析——概括事实、各条关联、对市场/政策/行业的影响；涵盖知名企业（维谛/美光/甲骨文/七姐妹等）财报与访华、关键人物（黄仁勋/马斯克/特朗普/英特尔/谷歌）、地缘政治、机构研报、商业航天/星链、美联储、股市、能源、黄金、石油、军事、AI 等，按重要性组织。
3. 预测部分（后半）：基于今日情报，对接下来几日或一周内的可能动向做简明展望。
4. 总字数约 800～1200 字；直接输出整段文字，不要小标题与编号列表。

今日条目：
{block}

请直接输出一长段深度总结与展望："""
    messages = [
        {"role": "system", "content": "你擅长写详实的每日情报深度总结，并基于情报给出简明展望与预测。"},
        {"role": "user", "content": prompt},
    ]
    result = _call_github_models_with_reasoning(
        messages, max_tokens=max_tokens, model=model, max_retries=3
    )
    return result


def generate_report_summary(items: List[Dict]) -> Optional[str]:
    """
    根据当日所有条目生成一长段报告总结（含今日要点与展望预测），用于放在报告最前面。
    优先使用 DeepSeek-R1 带思考；若未配置或失败则回退到普通模型。
    """
    result = generate_report_summary_with_reasoning(items)
    if result.get("summary"):
        return result["summary"]
    # 回退：使用原有逻辑（普通模型）
    if not items:
        return None
    parts = []
    for i, item in enumerate(items[:40], 1):
        title = (item.get("title") or "")[:80]
        summary = item.get("summary") or item.get("content") or ""
        summary = (summary[:150] if summary else "").replace("\n", " ")
        cat = item.get("category", "")
        parts.append(f"[{i}] [{cat}] {title} | {summary}")
    block = "\n".join(parts)
    prompt = f"""你是一位全球科技与金融情报分析师。根据以下今日情报条目，写一长段「今日总结与展望」，要求深度分析、信息密度高。

要求：
1. 中文，整体为一长串连贯段落（不要分小节标题，不要列表符号）。
2. 总结部分（前半）：对今日情报做深度分析——不仅概括事实，还要点出各条之间的关联、对市场/政策/行业的影响、关键人物或机构的立场变化；涵盖商业航天/星链、美联储、股市、能源、黄金、石油、军事、AI、政要动态等，按重要性组织，信息密度高。
3. 预测部分（后半）：基于今日情报，对接下来几日或一周内的可能动向做简明展望（政策、市场、地缘、技术突破等），标注为基于现有信息的合理推断即可。
4. 总字数约 1000～1500 字，务必写足、不要过短；可多段连续，保持可读性。
5. 直接输出整段文字，不要「总结：」「预测：」等小标题，不要编号列表。

今日条目：
{block}

请直接输出一长段深度总结与展望（多段连续文字，约 1000～1500 字）："""
    messages = [
        {"role": "system", "content": "你擅长写详实的每日情报深度总结，并基于情报给出简明展望与预测。"},
        {"role": "user", "content": prompt},
    ]
    summary_cap = getattr(settings, "LLM_MAX_TOKENS", 12000) or 12000
    return _call_github_models(messages, max_tokens=min(summary_cap, 4500))


def generate_stock_analysis(items: List[Dict]) -> Optional[str]:
    """
    根据当日行情（大涨个股、今日涨跌）与当日情报，生成一段「涨跌原因简析」与「可关注/建议规避」建议。
    用于报告股票板块下方。
    """
    if not items:
        return None
    stock_items = [i for i in items if i.get("category") in ("大涨个股", "今日涨跌", "美股市场")]
    news_snippets = []
    for i in items[:50]:
        if i.get("category") in ("大涨个股", "今日涨跌", "美股市场"):
            continue
        t = (i.get("title") or "")[:60]
        c = (i.get("content") or i.get("summary") or "")[:80]
        if t or c:
            news_snippets.append(f"[{i.get('category', '')}] {t} | {c}")
    stock_lines = []
    for i in stock_items:
        sym = i.get("symbol") or i.get("name") or i.get("title", "")
        chg = i.get("change_pct")
        if chg is not None:
            stock_lines.append(f"{sym}: {chg:+.2f}%")
    stock_block = "\n".join(stock_lines[:30]) if stock_lines else "（无当日行情）"
    news_block = "\n".join(news_snippets[:25]) if news_snippets else "（无）"
    prompt = f"""你是一位美股分析师。根据以下「当日行情」与「当日要闻摘要」，写一段简短中文分析（约 300～500 字），包含：
1. 涨跌原因简析：结合要闻解释今日哪些板块/个股为何涨、为何跌。
2. 可关注方向：推荐 1～3 类或具体标的（如某行业、某龙头），并简述理由。
3. 建议规避方向：哪些类型或标的建议减仓/观望，并简述理由。

要求：客观、基于给定信息，不要编造；直接输出分析正文，不要小标题与编号。

【当日行情】
{stock_block}

【当日要闻摘要】
{news_block}

请直接输出分析正文："""
    messages = [
        {"role": "system", "content": "你是美股分析师，根据行情与新闻写简短的涨跌原因与关注/规避建议。"},
        {"role": "user", "content": prompt},
    ]
    max_tok = getattr(settings, "LLM_MAX_TOKENS", 4000) or 4000
    return _call_github_models(messages, max_tokens=min(max_tok, 800))
