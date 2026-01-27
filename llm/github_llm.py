"""
LLM 摘要模块
使用 GitHub 提供的模型 API（通过 models.inference.ai.azure.com）
"""
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
            
            # 检查 429 错误（限流）
            if response.status_code == 429:
                # 429 错误需要等待更长时间
                wait_time = 10 + (2 ** attempt)  # 基础10秒 + 指数退避
                logger.warning(f"GitHub Models API 限流（429），等待 {wait_time} 秒后重试（尝试 {attempt + 1}/{max_retries}）")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue  # 直接重试，不抛出异常
                else:
                    logger.error(f"摘要生成最终失败（限流）: {item.get('title', '')}")
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
    批量生成摘要
    
    Args:
        items: 数据项列表
        delay: 每次请求之间的延迟（秒），避免速率限制（默认1.2秒，避免429错误）
    
    Returns:
        添加了 summary 字段的数据项列表
    """
    summarized_items: List[Dict] = []
    
    for i, item in enumerate(items):
        logger.info(f"生成摘要 {i + 1}/{len(items)}: {item.get('title', '')[:50]}")
        summarized_item = summarize_item(item)
        summarized_items.append(summarized_item)
        
        # 延迟以避免速率限制（生产级：1.2秒延迟）
        # GitHub Models 免费版有速率限制，需要适当延迟
        if i < len(items) - 1:
            time.sleep(delay)
    
    return summarized_items
