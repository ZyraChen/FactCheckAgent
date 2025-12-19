# LangChain Lite 版本 - 轻量级

## 🎯 设计理念

这是 `debate_fact_checker_v2.0` 的 **LangChain 轻量级版本**。

**核心原则：**
- ✅ **完全保留原始 workflow**
- ✅ **只用 LangChain Chain 来组织 LLM 调用**
- ❌ **不使用** LangChain Tools
- ❌ **不使用** ReAct Agent
- ❌ **不改变**流程和架构

---

## 📁 项目结构

```
debate_fact_checker_v2.0/
├── langchain_lite/              # 🆕 LangChain Lite 版本
│   ├── chains/                  # LangChain Chains（仅用于 LLM 调用）
│   │   ├── pro_chain.py        # Pro Agent 查询生成
│   │   ├── con_chain.py        # Con Agent 查询生成
│   │   └── judge_chain.py      # Judge 判决生成
│   ├── workflow/                # Workflow（保留原始流程）
│   │   └── debate_workflow_lc.py
│   └── utils/
│       └── qwen_wrapper.py     # Qwen LLM Wrapper
│
├── main_langchain_lite.py       # 🆕 入口程序
├── simple_workflow.py           # 原版（保留）
└── LANGCHAIN_LITE_README.md     # 本文档
```

---

## 🔄 Workflow 对比

### 原版 (simple_workflow.py)

```python
# 每轮
pro_queries = pro_agent.generate_search_queries(...)  # 直接调用 Qwen
con_queries = con_agent.generate_search_queries(...)  # 直接调用 Qwen

# 搜索
results = jina.search(query)
evidence_pool.add_evidence(...)
arg_graph.add_evidence_node(...)

# 攻击检测
attacks = attack_detector.detect_attacks_for_round(...)
arg_graph.add_attacks(attacks)

# 判决
verdict = judge_agent.make_verdict(...)  # 直接调用 Qwen
```

### LangChain Lite 版本

```python
# 每轮
pro_queries = pro_chain.generate_queries(...)  # 使用 LangChain Chain
con_queries = con_chain.generate_queries(...)  # 使用 LangChain Chain

# 搜索（完全相同）
results = jina.search(query)
evidence_pool.add_evidence(...)
arg_graph.add_evidence_node(...)  # Evidence = 节点

# 攻击检测（完全相同）
attacks = attack_detector.detect_attacks_for_round(...)
arg_graph.add_attacks(attacks)

# 判决
verdict = judge_chain.make_verdict(...)  # 使用 LangChain Chain
```

**差异**：
- ✅ 只替换了 LLM 调用部分（`generate_queries`, `make_verdict`）
- ✅ 流程完全相同
- ✅ 数据结构完全相同（Evidence 作为节点）

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install langchain langchain-core
```

### 2. 运行单个 Claim

```bash
python main_langchain_lite.py --claim "欧盟计划在2030年全面禁止销售燃油车。" --rounds 2
```

### 3. 批量处理

```bash
python main_langchain_lite.py --dataset data/dataset_part_1.json --max-samples 5
```

---

## 🏗️ 技术细节

### 1. ProQueryChain

**功能**：生成支持 claim 的搜索查询

**实现**：
```python
class ProQueryChain:
    def __init__(self, llm):
        self.prompt_template = PromptTemplate(...)
        self.chain = LLMChain(llm=llm, prompt=self.prompt_template)

    def generate_queries(self, claim, round_num, opponent_evidences, existing_queries):
        result = self.chain.invoke({...})
        return parsed_queries
```

**好处**：
- ✅ Prompt 和逻辑分离
- ✅ 易于调试和修改 Prompt
- ✅ Output Parsing 规范化

### 2. ConQueryChain

结构同 ProQueryChain，只是 Prompt 不同（反驳 claim）。

### 3. JudgeChain

**功能**：
1. 判断每个证据的立场（support/refute）
2. 生成最终判决

**实现**：
```python
class JudgeChain:
    def __init__(self, llm):
        self.stance_chain = LLMChain(...)  # 判断立场
        self.verdict_chain = LLMChain(...)  # 生成判决

    def make_verdict(self, claim, accepted_evidences, all_evidences_count):
        # 1. 判断每个证据立场
        for ev in accepted_evidences:
            stance = self.determine_stance(claim, ev)

        # 2. 计算强度
        support_strength = ...
        refute_strength = ...

        # 3. 生成判决
        result = self.verdict_chain.invoke({...})
        return Verdict(...)
```

---

## 📊 与原版对比

| 特性 | 原版 (simple_workflow) | LangChain Lite |
|------|------------------------|----------------|
| **Workflow** | Pro/Con 查询 → 搜索 → 攻击检测 → 判决 | **完全相同** |
| **Evidence 节点** | ✓ | ✓ |
| **攻击检测** | ✓ | ✓ |
| **LLM 调用方式** | 直接调用 `llm.chat()` | LangChain Chain |
| **Prompt 管理** | 字符串拼接 | PromptTemplate |
| **输出解析** | 手动解析 | OutputParser |
| **代码复杂度** | 简单 | 稍复杂（多了 Chain 层） |
| **可维护性** | 中 | 高（Prompt 独立管理） |
| **性能** | ⚡ 快 | ⚡ 快（几乎无差异） |

---

## ✅ 优势

### vs 原版
1. ✅ **Prompt 管理更规范**：使用 PromptTemplate，易于修改和版本控制
2. ✅ **输出解析更可靠**：OutputParser 统一处理
3. ✅ **符合 LangChain 生态**：未来可轻松集成其他 LangChain 组件

### vs 完整 LangChain 版本（Tools + ReAct）
1. ✅ **保留原始流程**：不改变您的架构
2. ✅ **更快速**：不需要 ReAct 推理循环
3. ✅ **更可控**：流程固定，不会有 Agent 自主决策的不确定性
4. ✅ **更轻量**：不需要 Tools，代码更简洁

---

## 🆚 适用场景

| 场景 | 推荐版本 |
|------|----------|
| **生产环境** | 原版 或 LangChain Lite |
| **大规模处理** | 原版（最快） |
| **需要 Prompt 管理** | LangChain Lite |
| **集成 LangChain 生态** | LangChain Lite |
| **需要 Agent 自主决策** | 完整 LangChain 版本（已删除） |
| **研究新范式** | 完整 LangChain 版本（已删除） |

---

## 📝 示例

### 运行示例

```bash
$ python main_langchain_lite.py --claim "程立目前是蚂蚁集团的董事。" --rounds 2

================================================================================
LangChain Lite 辩论系统（保留原始 workflow）
================================================================================

Claim: 程立目前是蚂蚁集团的董事。

======================================================================
第 1/2 轮
======================================================================

[查询生成]
Pro 查询: ['蚂蚁集团官方网站董事会成员名单2024']
Con 查询: ['蚂蚁集团现任董事会成员名单']

[证据搜索]
搜索: [PRO] 蚂蚁集团官方网站董事会成员名单2024
  ✓ 证据节点: pro_1_a1b2c3d4 (可信度:High, 质量:0.85)
搜索: [CON] 蚂蚁集团现任董事会成员名单
  ✓ 证据节点: con_1_e5f6g7h8 (可信度:High, 质量:0.90)

[攻击检测]
✓ 新增 1 个攻击边

[本轮统计] Pro:1个, Con:1个, 总计:2个证据节点

... (第2轮)

================================================================================
Judge 判决
================================================================================

[立场分析] 判断证据立场...
  ✗ con_1_e5f6g7h8: 反对
  ✓ pro_1_a1b2c3d4: 支持

支持强度: 0.750, 反对强度: 0.800

================================================================================
📊 最终判决
================================================================================

判决: ✗ Refuted
置信度: 70%

推理过程:
--------------------------------------------------------------------------------
根据蚂蚁集团官方董事会名单，程立目前不在董事会成员中。虽然支持方找到了历史资料显示程立曾任董事，但反对方提供的最新官方名单更具时效性和权威性。

关键证据节点:
--------------------------------------------------------------------------------
• [con_1_e5f6g7h8] antgroup.com
  蚂蚁集团2024年最新董事会成员名单，不包含程立...
```

---

## 🔧 自定义

### 修改 Prompt

编辑 `langchain_lite/chains/pro_chain.py`:

```python
self.prompt_template = PromptTemplate(
    input_variables=[...],
    template="""你的自定义 Prompt

    {claim}
    {round_num}
    ...
    """
)
```

### 调整输出解析

编辑 `QueryOutputParser`:

```python
class QueryOutputParser(BaseOutputParser[List[str]]):
    def parse(self, text: str) -> List[str]:
        # 你的解析逻辑
        ...
```

---

## 📚 核心代码

### Workflow 主流程

见 `langchain_lite/workflow/debate_workflow_lc.py:run_debate_workflow_lc()`

关键点：
```python
# 1. 创建 Chains
pro_chain = ProQueryChain(llm=llm_wrapper)
con_chain = ConQueryChain(llm=llm_wrapper)
judge_chain = JudgeChain(llm=llm_wrapper)

# 2. 每轮辩论
for round_num in range(1, max_rounds + 1):
    # 生成查询（使用 Chain）
    pro_queries = pro_chain.generate_queries(...)
    con_queries = con_chain.generate_queries(...)

    # 搜索（保持原样）
    results = jina.search(query)
    evidence_pool.add_evidence(...)
    arg_graph.add_evidence_node(...)  # Evidence = 节点

    # 攻击检测（保持原样）
    attacks = attack_detector.detect_attacks_for_round(...)
    arg_graph.add_attacks(attacks)

# 3. 判决（使用 Chain）
verdict = judge_chain.make_verdict(...)
```

---

## ✅ 总结

**LangChain Lite 版本** = 原版 workflow + LangChain Chain（仅用于 LLM 调用）

- ✅ 保留您的架构（Evidence 节点、攻击检测、论辩图）
- ✅ 保留您的流程（搜索 → 攻击检测 → 反应 → 下一轮）
- ✅ 只是用 LangChain 来规范化 Prompt 和 LLM 调用

**推荐**：生产环境和需要 Prompt 管理的场景！
