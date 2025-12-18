"""
优先级计算
基于证据可信度计算论证节点的优先级
"""

from typing import List, Optional
from utils.models import Evidence


def calculate_priority(evidences: List[Optional[Evidence]]) -> float:
    """
    计算论证的优先级
    
    规则:
    - High credibility: 1.0
    - Medium credibility: 0.6
    - Low credibility: 0.3
    - 多条证据取平均
    
    返回: 0.0-1.0的优先级分数
    """
    if not evidences:
        return 0.5  # 默认中等优先级
    
    # 过滤None
    valid_evidences = [e for e in evidences if e is not None]
    if not valid_evidences:
        return 0.5
    
    credibility_scores = {
        "High": 1.0,
        "Medium": 0.6,
        "Low": 0.3
    }
    
    scores = [
        credibility_scores.get(e.credibility, 0.5)
        for e in valid_evidences
    ]
    
    # 计算加权平均(可以考虑数量加成)
    avg_score = sum(scores) / len(scores)
    
    # 数量加成(最多+0.1)
    quantity_bonus = min(0.1, len(valid_evidences) * 0.02)
    
    final_priority = min(1.0, avg_score + quantity_bonus)
    
    return round(final_priority, 3)


def compare_priority(priority_a: float, priority_b: float, threshold: float = 0.05) -> str:
    """
    比较两个优先级
    
    返回: "higher", "lower", "equal"
    """
    if abs(priority_a - priority_b) < threshold:
        return "equal"
    elif priority_a > priority_b:
        return "higher"
    else:
        return "lower"


# 测试
if __name__ == "__main__":
    from utils.models import Evidence
    from datetime import datetime
    
    # 测试证据
    evidence_high = Evidence(
        id="e1",
        content="Test",
        url="http://test.com",
        credibility="High",
        retrieved_by="pro",
        round_num=1,
        search_query="test",
        timestamp=datetime.now()
    )
    
    evidence_medium = Evidence(
        id="e2",
        content="Test2",
        url="http://test2.com",
        credibility="Medium",
        retrieved_by="pro",
        round_num=1,
        search_query="test",
        timestamp=datetime.now()
    )
    
    # 测试计算
    priority1 = calculate_priority([evidence_high])
    priority2 = calculate_priority([evidence_medium])
    priority3 = calculate_priority([evidence_high, evidence_medium])
    
    print(f"High evidence priority: {priority1}")
    print(f"Medium evidence priority: {priority2}")
    print(f"Combined priority: {priority3}")
    
    print(f"\nComparison: {compare_priority(priority1, priority2)}")
