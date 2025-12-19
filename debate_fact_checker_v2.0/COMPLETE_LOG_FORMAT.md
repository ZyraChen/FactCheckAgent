# 完整日志格式说明 (complete_log.json)

## 📋 概述

运行 `debate_fact_checker_v2.0` 后，会在 `output/` 目录生成 `complete_log.json`，包含完整的运行日志。

---

## 📊 JSON 格式

```json
{
  "claim": "原始 claim 文本",
  "ground_truth": "Supported/Refuted/NEI (数据集标签)",
  "timestamp": "2025-12-19T10:30:00.123456",

  "statistics": {
    "total_evidences": 12,
    "pro_evidences": 6,
    "con_evidences": 6,
    "total_attacks": 8,
    "accepted_evidences": 5,
    "defeated_evidences": 7
  },

  "evidences": {
    "all_evidences": [...],      // 所有证据节点
    "accepted_evidences": [...],  // 被接受的证据
    "defeated_evidences": [...]   // 被击败的证据
  },

  "argumentation": {
    "attack_edges": [...],        // 攻击关系
    "grounded_extension": [...]   // Grounded Extension
  },

  "verdict": {
    "decision": "Supported/Refuted/NEI",
    "confidence": 0.85,
    "reasoning": "判决推理过程...",
    "key_evidence_ids": [...],
    "pro_strength": 0.8,
    "con_strength": 0.3
  },

  "evaluation": {
    "predicted": "Supported",
    "ground_truth": "Refuted",
    "correct": false
  }
}
```

---

## 📝 详细字段说明

### 1. 基本信息

| 字段 | 类型 | 说明 |
|------|------|------|
| `claim` | string | 要核查的 claim |
| `ground_truth` | string | 数据集中的真实标签 (Supported/Refuted/NEI) |
| `timestamp` | string | 运行时间戳 (ISO 8601) |

---

### 2. statistics（统计信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_evidences` | int | 总证据节点数 |
| `pro_evidences` | int | Pro 检索的证据数 |
| `con_evidences` | int | Con 检索的证据数 |
| `total_attacks` | int | 攻击边总数 |
| `accepted_evidences` | int | 被接受的证据数 (Grounded Extension) |
| `defeated_evidences` | int | 被击败的证据数 |

---

### 3. evidences（证据详情）

#### 3.1 all_evidences（所有证据节点）

每个证据节点包含：

```json
{
  "id": "pro_1_a1b2c3d4",
  "content": "证据完整内容...",
  "url": "https://example.com/article",
  "source": "example.com",
  "credibility": "High/Medium/Low",
  "quality_score": 0.85,
  "priority": 0.90,
  "retrieved_by": "pro/con",
  "round_num": 1,
  "search_query": "搜索使用的查询词",
  "timestamp": "2025-12-19T10:30:00"
}
```

| 字段 | 说明 |
|------|------|
| `id` | 证据唯一ID |
| `content` | 证据完整文本内容 |
| `url` | 证据来源URL |
| `source` | 来源网站 |
| `credibility` | 可信度 (High/Medium/Low) |
| `quality_score` | 质量分数 (0-1) |
| `priority` | 优先级分数 = credibility × quality_score |
| `retrieved_by` | 谁检索的 (pro/con) |
| `round_num` | 第几轮检索的 |
| `search_query` | 使用的搜索查询 |
| `timestamp` | 检索时间戳 |

#### 3.2 accepted_evidences（被接受的证据）

被接受的证据（通过 Grounded Extension 计算）：

```json
{
  "id": "pro_1_a1b2c3d4",
  "agent": "pro",
  "priority": 0.90,
  "source": "example.com",
  "content_preview": "证据内容前200字..."
}
```

#### 3.3 defeated_evidences（被击败的证据）

被攻击击败的证据：

```json
{
  "id": "con_2_e5f6g7h8",
  "agent": "con",
  "priority": 0.65,
  "defeated_by": ["pro_1_a1b2c3d4", "pro_2_i9j0k1l2"]
}
```

---

### 4. argumentation（论辩信息）

#### 4.1 attack_edges（攻击关系）

证据节点之间的攻击边：

```json
{
  "from_evidence_id": "pro_2_xyz789",
  "from_agent": "pro",
  "from_priority": 0.90,
  "to_evidence_id": "con_1_abc123",
  "to_agent": "con",
  "to_priority": 0.65,
  "strength": 0.25,
  "rationale": "攻击理由: Pro的证据优先级更高，且内容更权威...",
  "round_num": 2
}
```

| 字段 | 说明 |
|------|------|
| `from_evidence_id` | 攻击者证据ID |
| `from_agent` | 攻击者所属agent (pro/con) |
| `from_priority` | 攻击者优先级 |
| `to_evidence_id` | 被攻击者证据ID |
| `to_agent` | 被攻击者所属agent |
| `to_priority` | 被攻击者优先级 |
| `strength` | 攻击强度 = 优先级差 |
| `rationale` | LLM 生成的攻击理由 |
| `round_num` | 攻击发生在第几轮 |

#### 4.2 grounded_extension

被接受的证据ID列表：

```json
["pro_1_a1b2c3d4", "pro_2_xyz789", "con_3_def456"]
```

---

### 5. verdict（判决结果）

最终判决信息：

```json
{
  "decision": "Supported",
  "confidence": 0.85,
  "reasoning": "根据被接受的证据，Pro方提供了更权威的来源...",
  "key_evidence_ids": ["pro_1_a1b2c3d4", "pro_2_xyz789"],
  "pro_strength": 0.85,
  "con_strength": 0.40,
  "total_evidences": 12,
  "accepted_evidences": 5
}
```

| 字段 | 说明 |
|------|------|
| `decision` | 判决结果 (Supported/Refuted/NEI) |
| `confidence` | 置信度 (0-1) |
| `reasoning` | 详细的推理过程（LLM生成） |
| `key_evidence_ids` | 关键证据ID列表 |
| `pro_strength` | 支持方强度 |
| `con_strength` | 反对方强度 |
| `total_evidences` | 总证据数 |
| `accepted_evidences` | 被接受的证据数 |

---

### 6. evaluation（评估信息）

与数据集真实标签的对比：

```json
{
  "predicted": "Supported",
  "ground_truth": "Refuted",
  "correct": false
}
```

| 字段 | 说明 |
|------|------|
| `predicted` | 系统预测结果 |
| `ground_truth` | 数据集真实标签 |
| `correct` | 是否预测正确 |

---

## 🚀 使用示例

### 单个 Claim

```bash
python main_simple.py --claim "程立目前是蚂蚁集团的董事。" --rounds 2
```

输出文件：
- `output/complete_log.json` - 完整日志
- `output/verdict.json` - 判决结果
- `output/argumentation_graph.json` - 论辩图

### 批量处理数据集

```bash
python main_simple.py --dataset data/dataset_part_1.json --max-samples 10
```

输出文件：
- `output/log_001.json` - 第1条的完整日志
- `output/log_002.json` - 第2条的完整日志
- ...
- `output/results.json` - 所有结果汇总
- `output/results_stats.json` - 统计信息

---

## 📊 完整日志示例

```json
{
  "claim": "程立目前是蚂蚁集团的董事。",
  "ground_truth": "Refuted",
  "timestamp": "2025-12-19T10:30:45.123456",

  "statistics": {
    "total_evidences": 4,
    "pro_evidences": 2,
    "con_evidences": 2,
    "total_attacks": 2,
    "accepted_evidences": 2,
    "defeated_evidences": 2
  },

  "evidences": {
    "all_evidences": [
      {
        "id": "pro_1_a1b2c3d4",
        "content": "蚂蚁集团2020年董事会名单包含程立...",
        "url": "https://example.com/2020-board",
        "source": "example.com",
        "credibility": "Medium",
        "quality_score": 0.75,
        "priority": 0.525,
        "retrieved_by": "pro",
        "round_num": 1,
        "search_query": "蚂蚁集团董事会成员程立",
        "timestamp": "2025-12-19T10:30:15"
      },
      {
        "id": "con_1_e5f6g7h8",
        "content": "蚂蚁集团2024年最新董事会名单不包含程立...",
        "url": "https://antgroup.com/board-2024",
        "source": "antgroup.com",
        "credibility": "High",
        "quality_score": 0.90,
        "priority": 0.90,
        "retrieved_by": "con",
        "round_num": 1,
        "search_query": "蚂蚁集团最新董事会名单2024",
        "timestamp": "2025-12-19T10:30:20"
      }
    ],

    "accepted_evidences": [
      {
        "id": "con_1_e5f6g7h8",
        "agent": "con",
        "priority": 0.90,
        "source": "antgroup.com",
        "content_preview": "蚂蚁集团2024年最新董事会名单不包含程立..."
      },
      {
        "id": "con_2_i9j0k1l2",
        "agent": "con",
        "priority": 0.85,
        "source": "sina.com.cn",
        "content_preview": "新浪财经报道程立已于2023年1月卸任..."
      }
    ],

    "defeated_evidences": [
      {
        "id": "pro_1_a1b2c3d4",
        "agent": "pro",
        "priority": 0.525,
        "defeated_by": ["con_1_e5f6g7h8"]
      }
    ]
  },

  "argumentation": {
    "attack_edges": [
      {
        "from_evidence_id": "con_1_e5f6g7h8",
        "from_agent": "con",
        "from_priority": 0.90,
        "to_evidence_id": "pro_1_a1b2c3d4",
        "to_agent": "pro",
        "to_priority": 0.525,
        "strength": 0.375,
        "rationale": "Con的证据来自官方网站，时效性更强（2024 vs 2020），且优先级更高",
        "round_num": 2
      }
    ],
    "grounded_extension": ["con_1_e5f6g7h8", "con_2_i9j0k1l2"]
  },

  "verdict": {
    "decision": "Refuted",
    "confidence": 0.85,
    "reasoning": "根据最新的官方信息，程立目前不是蚂蚁集团的董事。虽然历史资料显示他曾担任该职位，但2024年的官方董事会名单中已不包含程立，且新浪财经报道显示他于2023年1月卸任。反对方提供的证据更具时效性和权威性。",
    "key_evidence_ids": ["con_1_e5f6g7h8", "con_2_i9j0k1l2"],
    "pro_strength": 0.0,
    "con_strength": 0.875,
    "total_evidences": 4,
    "accepted_evidences": 2
  },

  "evaluation": {
    "predicted": "Refuted",
    "ground_truth": "Refuted",
    "correct": true
  }
}
```

---

## 🎯 日志分析建议

### 1. 查看证据质量

检查 `evidences.all_evidences` 中的 `credibility` 和 `quality_score`，评估证据的可靠性。

### 2. 分析攻击关系

查看 `argumentation.attack_edges`，理解为什么某些证据被击败。

### 3. 验证判决依据

对比 `verdict.key_evidence_ids` 和 `evidences.accepted_evidences`，确认判决基于哪些证据。

### 4. 评估系统表现

检查 `evaluation.correct`，判断系统预测是否正确。

---

## 📌 注意事项

1. **时间戳格式**：所有时间戳使用 ISO 8601 格式
2. **优先级计算**：priority = credibility_score × quality_score
3. **攻击方向**：只有高优先级节点才能攻击低优先级节点
4. **Grounded Extension**：通过形式化语义计算得出的可接受证据集合

---

## 🔧 自定义日志

如需修改日志格式，编辑 `simple_workflow.py` 中的 `_build_complete_log()` 函数。
