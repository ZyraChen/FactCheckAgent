"""

测试输出格式 - 使用模拟数据

"""

import uuid

from datetime import datetime

from utils.models import Evidence, Verdict, AttackEdge

from core.evidence_pool import EvidencePool

from core.argumentation_graph import ArgumentationGraph


# 创建模拟证据

def create_mock_evidence(agent: str, round_num: int, content: str, credibility: str = "High"):
    """创建模拟证据"""

    evidence_id = f"{agent}_{round_num}_{uuid.uuid4().hex[:8]}"

    return Evidence(

        id=evidence_id,

        content=content,

        url=f"https://example.com/{evidence_id}",

        title=f"证据 {evidence_id}",

        source="example.com",

        credibility=credibility,

        retrieved_by=agent,

        round_num=round_num,

        search_query=f"测试查询 {agent} 第{round_num}轮",

        timestamp=datetime.now(),

        quality_score=0.8

    )


# 创建测试场景

claim = "欧盟计划在2030年全面禁止销售燃油车。"

evidence_pool = EvidencePool()

arg_graph = ArgumentationGraph(claim)

# 添加证据

e1 = create_mock_evidence("pro", 1,
                          "欧盟委员会官方宣布2030年将全面禁止燃油车销售，这是其绿色新政的重要组成部分。根据最新政策文件，所有成员国必须在2030年之前停止销售新的燃油车。",
                          "High")

e2 = create_mock_evidence("pro", 1,
                          "多家汽车制造商已经开始为2030年燃油车禁令做准备，加大对电动车的投资。这表明行业已经认可了这一政策方向。",
                          "Medium")

e3 = create_mock_evidence("con", 1,
                          "欧盟最新修订的政策显示，2030年的禁令实际上是2035年，而不是2030年。原定的2030年目标已经被推迟。",
                          "High")

e4 = create_mock_evidence("con", 2,
                          "欧盟委员会在压力下允许使用合成燃料的车辆可以豁免禁令，这意味着并非完全禁止所有燃油车。",
                          "High")

e5 = create_mock_evidence("pro", 2,
                          "尽管存在豁免条款，但主流燃油车仍将在2035年被禁止销售。合成燃料豁免只是很小的例外情况。",
                          "Medium")

for e in [e1, e2, e3, e4, e5]:
    evidence_pool.add_evidence(e)

    arg_graph.add_evidence_node(e)

# 添加攻击关系

attack1 = AttackEdge(

    from_evidence_id=e3.id,

    to_evidence_id=e1.id,

    strength=0.9,

    rationale="Con证据指出禁令年份是2035年而不是2030年，直接反驳了Pro证据关于2030年禁令的说法。",

    round_num=1

)

attack2 = AttackEdge(

    from_evidence_id=e4.id,

    to_evidence_id=e2.id,

    strength=0.7,

    rationale="合成燃料豁免条款削弱了全面禁令的说法，因为仍有部分燃油车可以继续销售。",

    round_num=2

)

arg_graph.add_attacks([attack1, attack2])

# 计算 Grounded Extension

accepted_ids = arg_graph.compute_grounded_extension()

# 创建模拟判决

verdict = Verdict(

    decision="Refuted",

    confidence=0.75,

    reasoning="经过分析双方提供的证据，发现支持2030年禁令的证据主要来自早期政策声明，但更权威的反方证据显示，实际的禁令年份是2035年而非2030年。此外，欧盟还允许使用合成燃料的车辆豁免，因此并非'全面'禁止。综合来看，原claim中关于'2030年'和'全面禁止'两个关键点都不准确。",

    key_evidence_ids=[e3.id, e4.id],

    accepted_evidence_ids=list(accepted_ids),

    pro_strength=0.45,

    con_strength=0.80,

    total_evidences=5,

    accepted_evidences=len(accepted_ids)

)

# 导入输出函数

from simple_workflow import _print_debate_summary, _print_final_report

# 测试输出

print("=" * 80)

print("测试辩论总结输出")

print("=" * 80)

_print_debate_summary(claim, evidence_pool, arg_graph)

print("\n\n" + "=" * 80)

print("测试最终报告输出")

print("=" * 80)

_print_final_report(claim, evidence_pool, arg_graph, verdict)