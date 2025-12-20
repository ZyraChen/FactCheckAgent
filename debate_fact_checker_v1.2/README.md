# 双Agent辩论式事实核查系统

基于论证推理(Argumentation Reasoning)的大模型事实核查框架

## 系统架构

```
输入Claim → 3轮辩论(Pro vs Con) → 论辩图构建 → Judge判决 → 输出Verdict
```

### 核心特点

1. **双Agent辩论**: Pro和Con独立搜索证据,动态构建论证
2. **论辩图**: 形式化建模论证之间的攻击关系(仅高优先级→低优先级)
3. **Grounded Semantics**: 使用形式化语义计算可接受论证集
4. **可解释性**: 提供完整的推理链路和证据溯源

## 安装

```bash
# 克隆项目
cd debate_fact_checker_v1.2

# 安装依赖
pip install -r requirements.txt

# 配置API Keys
export ANTHROPIC_API_KEY="your-key"
export JINA_API_KEY="your-key"
```

## 使用方法

### 1. 单个Claim核查

```bash
python main.py --claim "冥王星距太阳最远约为74亿公里。" --rounds 3
```

### 2. 批量处理数据集

```bash
python main.py --dataset data/dataset_part_1.json --output output/results.json --max-samples 10
```

### 3. Python API

```python
import asyncio
from main import run_debate_system

claim = "欧盟计划在2030年全面禁止销售燃油车。"
verdict = asyncio.run(run_debate_system(claim, max_rounds=3))

print(f"判决: {verdict.decision}")
print(f"置信度: {verdict.confidence}")
print(f"推理: {verdict.reasoning}")
```

## 输出文件

- `output/argumentation_graph.json`: 论辩图(节点+边)
- `output/verdict.json`: 判决结果
- `output/results.json`: 批量处理结果

## 项目结构

```
debate_fact_checker/
├── core/               # 核心数据结构
│   ├── argumentation_graph.py
│   └── evidence_pool.py
├── agents/             # Agent实现
│   ├── pro_agent.py
│   ├── con_agent.py
│   └── judge_agent.py
├── tools/              # 工具函数
│   ├── jina_search.py
│   ├── priority_calculator.py
│   └── attack_detector.py
├── reasoning/          # 推理引擎
│   └── semantics.py
├── llm/                # LLM接口
│   └── claude_client.py
└── main.py             # 主程序
```

## 工作流程

### 每一轮辩论:

1. **搜索阶段**
   - Pro和Con并行生成搜索查询
   - 调用Jina Search检索证据
   - 证据加入共享证据池

2. **论证构建**
   - Pro Agent从证据池筛选证据,构建支持论证
   - Con Agent看到Pro的新论证,构建反驳论证
   - 新论证节点加入论辩图

3. **攻击关系更新**
   - 检测高优先级节点对低优先级节点的攻击
   - 添加攻击边到论辩图

### 最终判决:

1. **计算Grounded Extension**: 找出可接受的论证集合
2. **评估双方强度**: 基于可接受论证的优先级和数量
3. **生成判决**: Supported / Refuted / NEI
4. **提取证据链**: 关键证据和推理路径

## 配置

编辑 `config.py` 修改系统参数:

- `MAX_DEBATE_ROUNDS`: 辩论轮次(默认3)
- `MAX_SEARCH_QUERIES_PER_AGENT`: 每轮搜索词数量
- `LLM_MODEL`: 使用的Claude模型
- 等等

## 示例输出

```json
{
  "decision": "Refuted",
  "confidence": 0.85,
  "reasoning": "根据权威来源的证据,欧盟的燃油车禁令目标年份为2035年而非2030年...",
  "key_evidence": ["e_con_1_a3f2", "e_con_2_b4e1"],
  "argument_analysis": {
    "pro_strength": 0.45,
    "con_strength": 0.82,
    "accepted_pro_args": 1,
    "accepted_con_args": 3
  }
}
```

