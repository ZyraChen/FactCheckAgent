
baseline测试当前数据集的claim，给出判决verdict和判决理由justification，然后计算以下几个指标：
(1)Verdict Accuracy：LLM最终给出的判决标签的准确度，
(2)Evidence F1: LLM给出的判决理由与真实标注的判决理由的匹配程度。
a. Macro-F1: 分别对于每种判决结果检测。
b. Micro-F1: 对于所有数据检测。
(4)Explanation Correctness：模型的解释（justification）中是否出现逻辑错误、虚构、矛盾、错误引用、错误推理等缺陷。解释是否包含真实知识，解释内容是否事实正确？有没有胡编乱造？有没有引入错误知识？
(5)Score：综合得分，explanation correctness，Evidence F1和verdict accuracy一起判断。













# LLM Baseline测试脚本使用说明

### 1️⃣ Verdict Accuracy（判决准确度）
- **定义**: LLM最终给出的判决标签与真实标注的匹配程度
- **计算**: 正确判决数 / 总测试数
- **分类统计**: 按Supported、Refuted、Not Enough Evidence分别计算准确率

### 2️⃣ Evidence Macro-F1（证据匹配-宏平均）
- **定义**: 对每种判决结果，LLM给出的判决理由与真实标注理由的匹配程度
- **计算**:
  - 提取真实标注中引用的证据来源
  - 提取LLM reasoning中引用的证据来源
  - 计算每个判决类别的F1分数
  - 对所有类别求平均
- **证据匹配方法**:
  - URL匹配
  - 来源名称匹配（如"Federal Reserve Bank"）
  - 数字/统计数据匹配
  - 模糊文本匹配（词重叠）

### 3️⃣ Evidence Micro-F1（证据匹配-微平均）
- **定义**: 对所有数据，LLM给出的判决理由与真实标注理由的匹配程度
- **计算**: 全局计算Precision、Recall和F1分数

### 4️⃣ Explanation Correctness（解释正确性）
- **定义**: 模型的解释（justification）是否存在缺陷
- **评估维度**:
  - 逻辑错误（logical_errors）
  - 虚构内容（fabrication）
  - 错误引用（wrong_citation）
  - 事实错误（factual_errors）
  - 知识错误（knowledge_errors）
  - 推理错误（reasoning_errors）
- **评分**: 0-100分，使用LLM自动评估
  - 90-100: 完全正确，无缺陷
  - 70-89: 基本正确，轻微瑕疵
  - 50-69: 部分正确，明显问题
  - 30-49: 严重错误，多处问题
  - 0-29: 完全错误，严重虚构

### 5️⃣ Overall Score（综合得分）
- **定义**: 综合考虑判决准确度、证据匹配度和解释正确性的总分
- **计算公式**:
  ```
  Score = 0.4 × Verdict_Accuracy + 0.3 × Evidence_F1 + 0.3 × (Explanation_Score/100)
  ```


---

##  输出文件

### 1. `enhanced_test_results.json`
完整的测试结果，包含：
- 所有评估指标
- 每条数据的详细结果
- LLM的判决、推理和评分

### 2. `error_analysis.json`
错误分析，包含三类错误：
- **verdict_errors**: 判决错误的数据
- **low_evidence_f1**: 证据匹配度低（<0.3）的数据
- **low_explanation_score**: 解释得分低（<50分）的数据

---

---

##  关键组件说明

### EvidenceMatcher 类
负责证据匹配评估：
- `extract_evidence_from_justification()`: 从真实标注中提取证据
- `extract_evidence_from_llm_reasoning()`: 从LLM推理中提取证据
- `calculate_evidence_f1()`: 计算F1分数
- `_fuzzy_match()`: 模糊匹配两个文本

### ExplanationEvaluator 类
负责解释质量评估：
- 使用LLM对LLM的输出进行评估
- 检测6种类型的错误
- 给出0-100分的评分

### EnhancedLLMFactChecker 类
主要测试类：
- `test_single_claim()`: 测试单条数据
- `calculate_metrics()`: 计算所有指标
- `print_report()`: 打印评估报告
- `save_results()`: 保存完整结果
- `save_error_analysis()`: 保存错误分析

---

## 调优建议

### 1. 证据匹配阈值调整
在 `EvidenceMatcher._fuzzy_match()` 中调整 `threshold` 参数：
```python
def _fuzzy_match(text1: str, text2: str, threshold: float = 0.3) -> bool:
```
- 提高阈值（如0.5）：更严格的匹配
- 降低阈值（如0.2）：更宽松的匹配

### 2. 综合得分权重调整
在 `test_single_claim()` 中调整权重：
```python
overall_score = (0.4 * verdict_score +     # Verdict权重
                0.3 * evidence_score +      # Evidence权重
                0.3 * explanation_score)    # Explanation权重
```

### 3. LLM搜索配置
```python
# 关闭搜索（仅基于LLM知识）
tester = EnhancedLLMFactChecker(
    api_key=API_KEY,
    dataset_path=DATASET_PATH,
    enable_search=False
)
```
        try:
            # 修复后的prompt - 字段名统一，JSON格式正确
            prompt = f"""You are a professional fact-checker with access to search capabilities. Use web search to verify the following claim.

Claim: "{claim}"

CRITICAL REQUIREMENTS:
1. Search for relevant, credible information about this claim
2. In your justification, you MUST cite specific sources:
   - Use formats like: "According to [Source Name]..."
   - Include URLs in evidence sources
   - Cite specific numbers, dates, and statistics

3. Provide your verdict as one of these exact terms:
   - "Supported" (if the claim is true based on evidence)
   - "Refuted" (if the claim is false based on evidence)
   - "Not Enough Evidence" (if you cannot find sufficient information)

4. Provide a complete justification (4-6 sentences with explicit source citations)

5. Provide the evidence sources you used, including:
   - content: Primary content of the evidence
   - url: The authentic URL
   - credibility: "High" (government, academic, mainstream media) | "Medium" (industry reports, local news) | "Low" (social media, unverified)

GOOD EXAMPLE:
{{
   "claim": "倪行军目前是蚂蚁集团的董事。",
    "verdict": "Refuted",
    "justification": "错误，公开资料显示，倪行军长期在蚂蚁集团担任首席技术官、资深副总裁以及技术战略委员会主席等管理岗位，并且自 2020 年起曾担任蚂蚁集团执行董事（Executive Director）。但后续董事会调整中，蚂蚁集团官网及多家媒体报道均指出：首席技术官倪行军不再担任蚂蚁集团执行董事，其董事席位由首席财务官韩歆毅接任，当前蚂蚁集团官网的领导层页面列出倪行军的头衔为“资深副总裁、技术战略委员会主席”，不再列入董事会成员，因此将其称为“目前是蚂蚁集团的董事”与最新结构不符。",
    "evidence_sources": [
      {{
        "content": "蚂蚁集团(688688)公司高管 – 新浪财经（说明倪行军自 2020 年 7 月起担任蚂蚁集团执行董事、自 2020 年 8 月起担任首席技术官，但该信息主要反映的是起任时间与曾任职务。）",
        "url": "https://money.finance.sina.com.cn/corp/view/vCI_CorpManagerInfo.php?stockid=688688&Pcode=30501025&Name=%C4%DD%D0%D0%BE%FC",
        "credibility": "Medium"
      }},
      {{
        "content": "蚂蚁集团董事会调整：韩歆毅接替倪行军出任执行董事 – 电商行业媒体报道指出，根据蚂蚁集团官网披露，首席技术官倪行军不再担任公司执行董事，由首席财务官韩歆毅接任，其后董事会成员名单中不再包含倪行军。",
        "url": "https://www.pai.com.cn/207021.html",
        "credibility": "Medium"
      }},
      {{
        "content": "Xingjun NI – Senior Vice President, Chairman of Technology Strategy Committee – Ant Group 官方英文页面（介绍倪行军目前的职务为蚂蚁集团资深副总裁、技术战略委员会主席，同时担任 OceanBase 董事长，没有将其列为 Ant Group 董事会成员。）",
        "url": "https://www.antgroup.com/en/about/leadership/xingjun-ni",
        "credibility": "High"
      }}
    ],
}}

Respond ONLY with a valid JSON object in this exact format, The language of the response content must be consistent with the claim.:
{{
  "claim": "the original claim text",
  "verdict": "Supported" | "Refuted" | "Not Enough Evidence",
  "justification": "Your detailed reasoning with source citations",
  "confidence": "High" | "Medium" | "Low",
  "evidence_sources": [
    {{
      "content": "Evidence description",
      "url": "URL",
      "credibility": "High" | "Medium" | "Low"
    }}
  ]
}}

Do not include any text outside the JSON object."""
