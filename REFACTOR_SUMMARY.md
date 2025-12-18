# 重构总结

## 重构完成时间
2025-12-18

## 问题分析

原代码存在以下问题：

### 1. 数据模型混乱
- `utils/models.py` 定义了 Evidence (Pydantic)
- `core/evidence_pool.py` 又定义了 Evidence (dataclass)
- 类型不一致导致序列化/反序列化困难

### 2. Judge Agent重复代码
- `judge_agent.py` 包含大量重复的方法定义
- 同一个方法出现两次，代码冗余严重

### 3. 架构不一致
- ArgumentationGraph 既用 Evidence 又用 ArgumentNode
- reasoning/semantics.py 假设有 ArgumentNode
- 实际运行时类型不匹配

### 4. NEI判决过多
- 即使有明显证据也判断为NEI
- `results.json` 显示0%准确率
- 判决逻辑过于保守

### 5. Commit信息不清晰
- 所有commit都是"1"
- 难以追踪历史变更

## 重构方案

### 1. 统一数据模型

**修改文件**: `utils/models.py`, `core/evidence_pool.py`

```python
# 只使用一套Evidence定义
class Evidence(BaseModel):
    id: str
    content: str
    url: str
    credibility: Literal["High", "Medium", "Low"]
    retrieved_by: Literal["pro", "con"]
    quality_score: float = 0.0

    def get_priority(self) -> float:
        """优先级 = 可信度 * 质量分数"""
```

**改进**:
- 移除dataclass版本的Evidence
- 统一使用Pydantic模型
- 添加 `model_dump()` 方法支持序列化

### 2. 重构核心模块

**EvidencePool** (`core/evidence_pool.py`)
```python
class EvidencePool:
    def add_evidence(self, evidence: Evidence)
    def get_by_agent(self, agent: str) -> List[Evidence]
    def get_high_quality(self, min_score: float) -> List[Evidence]
    def to_dict(self) -> Dict  # 新增序列化
    def from_dict(cls, data: Dict) -> EvidencePool  # 新增反序列化
```

**ArgumentationGraph** (`core/argumentation_graph.py`)
```python
class ArgumentationGraph:
    evidence_nodes: Dict[str, Evidence]  # 只用Evidence
    attack_edges: List[AttackEdge]

    def compute_grounded_extension(self) -> Set[str]
    def to_dict(self) -> Dict
    def from_dict(cls, data: Dict) -> ArgumentationGraph
```

### 3. 重写Agent

**ProAgent** (`agents/pro_agent.py`)
```python
class ProAgent:
    def generate_search_queries(
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[str]
```

**ConAgent** (`agents/con_agent.py`)
```python
class ConAgent:
    def generate_search_queries(
        round_num: int,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> List[str]
```

**JudgeAgent** (`agents/judge_agent.py`)
```python
class JudgeAgent:
    def make_verdict(
        claim: str,
        arg_graph: ArgumentationGraph,
        evidence_pool: EvidencePool
    ) -> Verdict

    def _make_decision(
        pro_accepted: List[Evidence],
        con_accepted: List[Evidence],
        pro_strength: float,
        con_strength: float
    ) -> tuple[str, float]
```

**判决逻辑改进**:
```python
# 1. 一方没有证据 → 另一方胜
if not pro_accepted:
    return "Refuted", 0.6-0.9

# 2. 强度差>15% → 强者胜
if strength_diff > 0.15:
    return winner, 0.6-0.9

# 3. 比较最高优先级证据
if max_pro > max_con + 0.1:
    return "Supported", 0.6

# 4. 比较数量
if len(pro) > len(con) + 1:
    return "Supported", 0.55

# 5. 最后才NEI
return "NEI", 0.5
```

### 4. 优化攻击检测

**AttackDetector** (`tools/attack_detector.py`)

```python
def detect_attacks_for_round(
    arg_graph: ArgumentationGraph,
    round_num: int
) -> List[AttackEdge]:
    # 1. 获取本轮新证据
    # 2. 与对方证据比较
    # 3. 优先级差>5%才攻击
    # 4. 使用LLM判断矛盾
    # 5. 降级策略: 基于可信度
```

### 5. 简化工作流

**simple_workflow.py** (新文件)
```python
def run_debate_workflow(claim: str, max_rounds: int = 3) -> dict:
    # 1. 初始化
    # 2. 多轮辩论
    #    - 生成查询
    #    - 搜索证据
    #    - 检测攻击
    # 3. Judge判决
    # 4. 返回结果
```

**main_simple.py** (新文件)
```bash
# 单个claim
python main_simple.py --claim "..." --rounds 3

# 批量测试
python main_simple.py --dataset data/dataset_part_1.json --max-samples 5
```

## 重构结果

### 文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| utils/models.py | 重写 | 统一数据模型 |
| core/evidence_pool.py | 重写 | 简化+序列化 |
| core/argumentation_graph.py | 重写 | 统一节点类型 |
| agents/pro_agent.py | 重写 | 简化接口 |
| agents/con_agent.py | 重写 | 简化接口 |
| agents/judge_agent.py | 重写 | 移除重复,改进判决 |
| tools/attack_detector.py | 重写 | 优化检测逻辑 |
| simple_workflow.py | 新增 | 简化工作流 |
| main_simple.py | 新增 | 新主程序 |
| README_REFACTORED.md | 新增 | 完整文档 |

### 代码统计

```
10 files changed
+1033 insertions
-923 deletions
```

### 关键改进

1. ✅ **数据一致性** - 统一使用Pydantic模型
2. ✅ **代码质量** - 移除重复,清晰结构
3. ✅ **判决准确率** - 改进NEI逻辑
4. ✅ **可维护性** - 简化架构,清晰注释
5. ✅ **文档完善** - README_REFACTORED.md

## 使用示例

### 快速测试

```bash
cd debate_fact_checker_v2.0

# 单个claim
python main_simple.py --claim "欧盟计划在2030年全面禁止销售燃油车。"

# 批量测试
python main_simple.py --dataset data/dataset_part_1.json --max-samples 2
```

### Python调用

```python
from simple_workflow import run_debate_workflow

result = run_debate_workflow("程立目前是蚂蚁集团的董事。", max_rounds=3)

print(f"判决: {result['verdict']['decision']}")
print(f"置信度: {result['verdict']['confidence']}")
print(f"推理: {result['verdict']['reasoning']}")
```

## 技术亮点

### 1. 论辩图 (Argumentation Framework)
- 基于Dung的抽象论辩框架
- Grounded Extension计算
- 高优先级证据攻击低优先级证据

### 2. 证据质量评估
```python
credibility_score = {"High": 1.0, "Medium": 0.6, "Low": 0.3}
length_score = min(1.0, len(content) / 500)
quality = credibility_score * 0.7 + length_score * 0.3
priority = credibility * quality
```

### 3. 判决策略
- 多维度: 强度、优先级、数量
- 阈值: 0.15 (强度差), 0.1 (优先级差)
- 分级置信度: 0.3-0.9

## 下一步建议

### 短期优化
1. **证据相关性** - 使用LLM评估证据与claim的相关性
2. **并行搜索** - 异步调用提高速度
3. **缓存机制** - 避免重复搜索
4. **日志系统** - 详细的调试日志

### 长期优化
1. **可视化** - 论辩图可视化界面
2. **交互式** - 支持人工介入调整
3. **多模态** - 支持图片/表格证据
4. **持续学习** - 从判决结果学习改进

## 参考资料

### 论辩框架
- Dung, P. M. (1995). "On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games"
- Baroni, P., & Giacomin, M. (2009). "Semantics of abstract argument systems"

### 事实核查
- Thorne, J., & Vlachos, A. (2018). "Automated Fact Checking: Task formulations, methods and future directions"
- Popat, K., et al. (2017). "DeClarE: Debunking Fake News and False Claims using Evidence-Aware Deep Learning"

## Git信息

```
Branch: claude/review-changes-mjb0lfj6wi93xvo6-o2zwo
Commit: c837c47
Date: 2025-12-18
```

## 联系方式

如有问题请查看 `README_REFACTORED.md` 或提issue。
