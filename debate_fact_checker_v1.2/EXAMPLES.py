"""
使用示例
展示如何使用双Agent辩论系统
"""

# 示例1: 单个claim核查
example_1 = """
python main.py --claim "冥王星距太阳最远约为74亿公里。" --rounds 3
"""

# 示例2: 处理数据集(10条)
example_2 = """
python main.py --dataset data/dataset_part_1.json --output output/results.json --max-samples 10
"""

# 示例3: Python API使用
example_3 = """
import asyncio
from main import run_debate_system

async def test():
    claim = "欧盟计划在2030年全面禁止销售燃油车。"
    verdict = await run_debate_system(claim, max_rounds=3)
    
    print(f"判决: {verdict.decision}")
    print(f"置信度: {verdict.confidence:.2%}")
    print(f"推理: {verdict.reasoning}")
    print(f"关键证据数: {len(verdict.key_evidence)}")

asyncio.run(test())
"""

# 示例4: 自定义Agent行为
example_4 = """
from agents.pro_agent import ProAgent
from llm.claude_client import ClaudeClient

# 创建自定义Pro Agent
llm = ClaudeClient("your-api-key")
pro_agent = ProAgent("你的主张", llm)

# 生成搜索查询
queries = pro_agent.generate_search_queries(
    round_num=1,
    arg_graph=arg_graph,
    evidence_pool=evidence_pool
)

# 构建论证
arguments = pro_agent.construct_arguments(
    round_num=1,
    arg_graph=arg_graph,
    evidence_pool=evidence_pool
)
"""

print("""
===============================================
双Agent辩论式事实核查系统 - 使用示例
===============================================

1. 安装依赖
-----------
pip install -r requirements.txt

2. 配置API Keys
---------------
export ANTHROPIC_API_KEY="your-key"
export JINA_API_KEY="your-key"

3. 运行测试
-----------
python test_basic.py

4. 使用示例
-----------

示例1 - 单个claim核查:
""" + example_1 + """

示例2 - 批量处理数据集:
""" + example_2 + """

示例3 - Python API:
""" + example_3 + """

5. 查看结果
-----------
- 论辩图: output/argumentation_graph.json
- 判决结果: output/verdict.json  
- 批量结果: output/results.json

6. 项目结构
-----------
debate_fact_checker_v1.2/
├── core/                  # 核心数据结构
│   ├── argumentation_graph.py    # 论辩图
│   └── evidence_pool.py           # 证据池
├── agents/                # Agent实现
│   ├── pro_agent.py               # 支持方
│   ├── con_agent.py               # 反对方
│   └── judge_agent.py             # 法官
├── tools/                 # 工具函数
│   ├── jina_search.py             # Jina搜索
│   ├── priority_calculator.py    # 优先级计算
│   └── attack_detector.py        # 攻击检测
├── reasoning/             # 推理引擎
│   └── semantics.py               # 形式化语义
├── llm/                   # LLM接口
│   └── qwen_client.py           # Claude客户端
├── utils/                 # 工具模块
│   └── models.py                  # 数据模型
├── data/                  # 数据目录
│   └── dataset_part_1.json        # 数据集
├── output/                # 输出目录
├── main.py                # 主程序
├── config.py              # 配置文件
├── test_basic.py          # 基础测试
└── README.md              # 说明文档

7. 核心概念
-----------
- ArgumentNode: 论证节点(包含证据、优先级、立场)
- AttackEdge: 攻击边(仅高优先级→低优先级)
- EvidencePool: 双方共享的证据池
- Grounded Extension: 可接受的论证集合
- Verdict: 最终判决(Supported/Refuted/NEI)

8. 系统流程
-----------
每轮辩论:
  1. Pro和Con生成搜索查询
  2. 并行搜索并加入证据池
  3. Pro构建论证(先手)
  4. Con构建论证(后手,可见Pro新论证)
  5. 更新攻击关系(高优先级→低优先级)

最终判决:
  1. 计算Grounded Extension
  2. 评估双方论证强度
  3. 生成判决和推理过程
  4. 输出结果

===============================================
""")
