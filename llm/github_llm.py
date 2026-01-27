"""
LLM 摘要模块
支持使用 GitHub Token 访问 Hugging Face 免费模型 API
也支持 OpenAI API（gpt-4o-mini）作为备选
"""
import requests
import json
import time
from typing import List, Dict, Optional

from config import settings
from utils.logger import logger

def summarize_with_openai(item: Dict, max_retries: int = 3) -> Optional[str]:
    """
    使用 OpenAI API 生成中文摘要
    
    Args:
        item: 数据项字典
        max_retries: 最大重试次数
    
    Returns:
        中文摘要，失败返回 None
    """
    api_key = settings.GITHUB_MODELS_API_KEY  # 实际使用 OpenAI API key
    if not api_key:
        logger.warning("未配置 OpenAI API Key，跳过摘要生成")
        return None
    
    url = "https://api.openai.com/v1/chat/completions"
    
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
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": settings.LLM_MODEL,
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
            response.raise_for_status()
            
            result = response.json()
            summary = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if summary:
                return summary
            else:
                logger.warning(f"摘要生成返回空结果: {item.get('title', '')}")
                return None
                
        except requests.exceptions.RequestException as e:
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

def summarize_with_huggingface(item: Dict, max_retries: int = 3) -> Optional[str]:
    """
    使用 Hugging Face Inference API 生成中文摘要（免费方案）
    支持使用 GitHub Token 进行认证
    
    Args:
        item: 数据项字典
        max_retries: 最大重试次数
    
    Returns:
        中文摘要，失败返回 None
    """
    # 使用 GitHub Token 或 Hugging Face Token
    token = settings.GITHUB_MODELS_API_KEY  # 可以是 GitHub Token 或 HF Token
    if not token:
        logger.warning("未配置 Token，跳过摘要生成")
        return None
    
    # 使用支持中文的免费模型
    # 推荐使用：Qwen/Qwen2.5-0.5B-Instruct 或其他中文模型
    model_name = getattr(settings, 'HF_MODEL_NAME', 'Qwen/Qwen2.5-0.5B-Instruct')
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    
    # 构建 prompt
    prompt = f"""请将以下英文信息总结成简洁的中文摘要，要求：
1. 输出语言：中文
2. 风格：投资情报/晨报风格，客观、简洁
3. 只总结原始信息，不要猜测或扩展
4. 保持关键事实和数据
5. 长度控制在 100 字以内

原始信息：
标题：{item.get('title', '')}
内容：{item.get('content', '')}
来源：{item.get('source', '')}

请直接输出中文摘要："""
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.3,
            "return_full_text": False
        }
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            # Hugging Face API 可能返回 503（模型加载中），需要等待
            if response.status_code == 503:
                wait_time = response.json().get("estimated_time", 10)
                logger.info(f"模型加载中，等待 {wait_time} 秒...")
                time.sleep(min(wait_time, 30))
                continue
            
            response.raise_for_status()
            result = response.json()
            
            # 解析响应（格式可能是列表或字典）
            if isinstance(result, list) and len(result) > 0:
                summary = result[0].get("generated_text", "").strip()
            elif isinstance(result, dict):
                summary = result.get("generated_text", "").strip()
            else:
                summary = str(result).strip()
            
            if summary:
                # 清理输出，移除可能的 prompt 重复
                if prompt[:50] in summary:
                    summary = summary.split(prompt[:50])[-1].strip()
                return summary
            else:
                logger.warning(f"摘要生成返回空结果: {item.get('title', '')}")
                return None
                
        except requests.exceptions.RequestException as e:
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

def summarize_item(item: Dict, use_hf: bool = True) -> Dict:
    """
    为单个数据项生成摘要
    
    Args:
        item: 数据项字典
        use_hf: 是否使用 Hugging Face API（True，免费）或 OpenAI（False，需付费）
    
    Returns:
        添加了 summary 字段的数据项字典
    """
    # 优先使用 Hugging Face（免费），如果失败则尝试 OpenAI
    if use_hf:
        summary = summarize_with_huggingface(item)
        # 如果 HF 失败且配置了 OpenAI key，尝试 OpenAI
        if not summary and hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            logger.info("Hugging Face 失败，尝试使用 OpenAI...")
            summary = summarize_with_openai(item)
    else:
        summary = summarize_with_openai(item)
    
    # 如果摘要生成失败，使用原始内容的前100字
    if not summary:
        original_content = item.get("content", item.get("title", ""))
        summary = original_content[:100] + ("..." if len(original_content) > 100 else "")
    
    item["summary"] = summary
    return item

def summarize_batch(items: List[Dict], use_hf: bool = True, delay: float = 1.0) -> List[Dict]:
    """
    批量生成摘要
    
    Args:
        items: 数据项列表
        use_hf: 是否优先使用 Hugging Face API（免费）
        delay: 每次请求之间的延迟（秒），避免速率限制（HF 需要更长延迟）
    
    Returns:
        添加了 summary 字段的数据项列表
    """
    summarized_items: List[Dict] = []
    
    for i, item in enumerate(items):
        logger.info(f"生成摘要 {i + 1}/{len(items)}: {item.get('title', '')[:50]}")
        summarized_item = summarize_item(item, use_hf)
        summarized_items.append(summarized_item)
        
        # 延迟以避免速率限制（Hugging Face 免费 API 限制较严格）
        if i < len(items) - 1:
            time.sleep(delay)
    
    return summarized_items

