"""
简单测试脚本
用于快速测试系统是否正常工作
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def test_data_models():
    """测试数据模型"""
    print("测试数据模型...")
    from utils.models import Evidence, ArgumentNode, AttackEdge
    from datetime import datetime
    
    # 测试Evidence
    evidence = Evidence(
        id="test_e1",
        content="测试证据内容",
        url="https://test.com",
        credibility="High",
        retrieved_by="pro",
        round_num=1,
        search_query="测试查询",
        timestamp=datetime.now()
    )
    print(f"✓ Evidence: {evidence.id}")
    
    # 测试ArgumentNode
    node = ArgumentNode(
        id="test_n1",
        agent="pro",
        round=1,
        content="测试论证",
        evidence_ids=["test_e1"],
        priority=0.8,
        stance="support_claim"
    )
    print(f"✓ ArgumentNode: {node.id}")
    
    # 测试AttackEdge
    edge = AttackEdge(
        from_node_id="test_n1",
        to_node_id="test_n2",
        strength=0.5,
        rationale="测试攻击"
    )
    print(f"✓ AttackEdge: {edge.from_node_id} -> {edge.to_node_id}")
    
    print("✓ 数据模型测试通过\n")


def test_argumentation_graph():
    """测试论辩图"""
    print("测试论辩图...")
    from core.argumentation_graph import ArgumentationGraph
    from utils.models import ArgumentNode, AttackEdge
    
    graph = ArgumentationGraph("测试主张")
    
    # 添加节点
    n1 = ArgumentNode(
        id="n1", agent="pro", round=1, content="Pro论证1",
        evidence_ids=[], priority=0.5, stance="support_claim"
    )
    n2 = ArgumentNode(
        id="n2", agent="con", round=1, content="Con论证1",
        evidence_ids=[], priority=0.8, stance="refute_claim"
    )
    
    graph.add_nodes([n1, n2])
    print(f"✓ 添加了 {len(graph.nodes)} 个节点")
    
    # 添加攻击边
    edge = AttackEdge(
        from_node_id="n2",
        to_node_id="n1",
        strength=0.3,
        rationale="高优先级攻击低优先级"
    )
    graph.add_edges([edge])
    print(f"✓ 添加了 {len(graph.edges)} 条边")
    
    # 测试统计
    stats = graph.get_statistics()
    print(f"✓ 统计信息: {stats}")
    
    print("✓ 论辩图测试通过\n")


def test_evidence_pool():
    """测试证据池"""
    print("测试证据池...")
    from core.evidence_pool import EvidencePool
    from utils.models import Evidence
    from datetime import datetime
    
    pool = EvidencePool()
    
    # 添加证据
    e1 = Evidence(
        id="e1", content="证据1", url="http://test1.com",
        credibility="High", retrieved_by="pro", round_num=1,
        search_query="query1", timestamp=datetime.now()
    )
    e2 = Evidence(
        id="e2", content="证据2", url="http://test2.com",
        credibility="Medium", retrieved_by="con", round_num=1,
        search_query="query2", timestamp=datetime.now()
    )
    
    pool.add_evidence(e1)
    pool.add_evidence(e2)
    
    print(f"✓ 证据池大小: {len(pool)}")
    print(f"✓ Pro的证据: {len(pool.get_by_agent('pro'))}")
    print(f"✓ Con的证据: {len(pool.get_by_agent('con'))}")
    print(f"✓ 高可信度证据: {len(pool.get_high_credibility())}")
    
    print("✓ 证据池测试通过\n")


def test_priority_calculator():
    """测试优先级计算"""
    print("测试优先级计算...")
    from tools.priority_calculator import calculate_priority, compare_priority
    from utils.models import Evidence
    from datetime import datetime
    
    e_high = Evidence(
        id="e1", content="test", url="http://test.com",
        credibility="High", retrieved_by="pro", round_num=1,
        search_query="q", timestamp=datetime.now()
    )
    e_medium = Evidence(
        id="e2", content="test", url="http://test.com",
        credibility="Medium", retrieved_by="pro", round_num=1,
        search_query="q", timestamp=datetime.now()
    )
    
    p1 = calculate_priority([e_high])
    p2 = calculate_priority([e_medium])
    p3 = calculate_priority([e_high, e_medium])
    
    print(f"✓ High优先级: {p1}")
    print(f"✓ Medium优先级: {p2}")
    print(f"✓ 组合优先级: {p3}")
    print(f"✓ 比较结果: {compare_priority(p1, p2)}")
    
    print("✓ 优先级计算测试通过\n")


def test_semantics():
    """测试语义计算"""
    print("测试形式化语义...")
    from reasoning.semantics import compute_grounded_extension
    from core.argumentation_graph import ArgumentationGraph
    from utils.models import ArgumentNode, AttackEdge
    
    graph = ArgumentationGraph("测试")
    
    # 创建简单的论辩图
    n1 = ArgumentNode(
        id="n1", agent="pro", round=1, content="A1",
        evidence_ids=[], priority=0.5, stance="support_claim"
    )
    n2 = ArgumentNode(
        id="n2", agent="con", round=1, content="A2",
        evidence_ids=[], priority=0.8, stance="refute_claim"
    )
    n3 = ArgumentNode(
        id="n3", agent="pro", round=2, content="A3",
        evidence_ids=[], priority=0.9, stance="support_claim"
    )
    
    graph.add_nodes([n1, n2, n3])
    graph.add_edges([
        AttackEdge(from_node_id="n2", to_node_id="n1", strength=0.3, rationale="test"),
        AttackEdge(from_node_id="n3", to_node_id="n2", strength=0.1, rationale="test")
    ])
    
    extension = compute_grounded_extension(graph)
    print(f"✓ Grounded Extension: {extension}")
    print(f"✓ 可接受论证数: {len(extension)}")
    
    print("✓ 形式化语义测试通过\n")


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("开始运行测试")
    print("="*60 + "\n")
    
    try:
        test_data_models()
        test_argumentation_graph()
        test_evidence_pool()
        test_priority_calculator()
        test_semantics()
        
        print("="*60)
        print("✓ 所有测试通过!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
