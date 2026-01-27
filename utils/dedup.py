"""
去重工具
"""
import hashlib
from typing import List, Dict, Set

def generate_hash(item: Dict) -> str:
    """
    为数据项生成唯一哈希值
    
    Args:
        item: 数据项字典，必须包含 'url' 和 'title' 字段
    
    Returns:
        SHA256 哈希值（十六进制字符串）
    """
    # 使用 URL 和标题生成哈希
    url = item.get("url", "")
    title = item.get("title", "")
    content = f"{url}|{title}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()

def deduplicate_items(items: List[Dict]) -> List[Dict]:
    """
    对数据项列表进行去重
    
    Args:
        items: 数据项列表
    
    Returns:
        去重后的数据项列表（保留第一次出现的项）
    """
    seen_hashes: Set[str] = set()
    unique_items: List[Dict] = []
    
    for item in items:
        item_hash = generate_hash(item)
        if item_hash not in seen_hashes:
            seen_hashes.add(item_hash)
            unique_items.append(item)
    
    return unique_items

def deduplicate_by_category(items: List[Dict]) -> Dict[str, List[Dict]]:
    """
    按类别分组并去重
    
    Args:
        items: 数据项列表
    
    Returns:
        按类别分组的去重后数据项字典
    """
    categorized: Dict[str, List[Dict]] = {}
    
    for item in items:
        category = item.get("category", "未分类")
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(item)
    
    # 对每个类别去重
    for category in categorized:
        categorized[category] = deduplicate_items(categorized[category])
    
    return categorized

