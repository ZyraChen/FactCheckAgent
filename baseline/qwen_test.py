"""
增强版LLM Baseline测试脚本（改进版）
包含完整的评估指标：
1. Verdict Accuracy
2. Evidence Macro-F1
3. Evidence Micro-F1
4. Explanation Correctness
5. 综合Score

主要改进：
1. 更明确的prompt，强制LLM引用证据来源
2. 降低模糊匹配阈值从0.3到0.2
3. 改进证据提取逻辑，支持更多引用模式
4. 添加详细的debug信息，显示证据匹配过程
"""

import json
import time
import re
from typing import List, Dict, Tuple, Set
from collections import defaultdict
import openai
from sklearn.metrics import f1_score, precision_recall_fscore_support


class QwenPlus:
    """通义千问LLM（带搜索功能）"""

    def __init__(self, api_key):
        self.model = "qwen3-max"
        self.llm = openai.OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    def _cons_kwargs(self, messages: list[dict]) -> dict:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "timeout": 60,
        }
        return kwargs

    def completion(self, messages: list[dict], enable_thinking=False, return_json=False, enable_search=False) -> str:
        """
        调用LLM completion

        Args:
            messages: 消息列表
            enable_thinking: 是否开启思考模式
            return_json: 是否返回JSON格式
            enable_search: 是否开启联网搜索功能
        """
        response_format = {"type": "json_object"} if not enable_thinking and return_json else {"type": "text"}
        extra_body = {}

        if enable_search:
            extra_body = {
                "enable_thinking": enable_thinking,
                "enable_search": True,
                "search_options": {
                    "forced_search": True
                }
            }

        try:
            rsp = self.llm.chat.completions.create(
                **self._cons_kwargs(messages),
                extra_body=extra_body if enable_search else None,
                response_format=response_format
            )
        except openai.RateLimitError as e:
            print("    ⚠️  API请求超过限制，等待60秒...")
            time.sleep(60)
            rsp = self.llm.chat.completions.create(
                **self._cons_kwargs(messages),
                extra_body=extra_body if enable_search else None,
                response_format=response_format
            )
        except openai.APITimeoutError as e:
            print("    ⚠️  API请求超时，等待60秒...")
            time.sleep(60)
            rsp = self.llm.chat.completions.create(
                **self._cons_kwargs(messages),
                extra_body=extra_body if enable_search else None,
                response_format=response_format
            )

        return rsp.choices[0].message.content


class EvidenceMatcher:
    """证据匹配评估器（改进版）"""

    @staticmethod
    def extract_evidence_from_justification(justification: str, evidence_sources: List[Dict]) -> Set[str]:
        """
        从数据集的evidence_sources中提取Ground Truth证据

        这些就是数据集中标注的、用来支持判决的证据来源
        每个evidence_source包含：content（来源描述）、url、credibility

        返回：证据来源的集合（使用content字段作为标识）
        """
        referenced_sources = set()

        if not evidence_sources:
            return referenced_sources

        # 将数据集中的所有evidence_sources作为Ground Truth
        for ev_source in evidence_sources:
            content = ev_source.get('content', '')
            url = ev_source.get('url', '')

            # 优先使用content，如果没有则使用URL
            identifier = content if content else url
            if identifier:
                referenced_sources.add(identifier)

        return referenced_sources

    @staticmethod
    def extract_evidence_from_llm_reasoning(reasoning: str) -> Set[str]:
        """
        从LLM的reasoning中提取证据引用

        LLM需要在reasoning中明确引用来源，我们通过以下方式提取：
        1. URL链接
        2. 引用格式："According to X"、"X reported"等
        3. 数字和百分比（用于匹配统计数据）

        返回：LLM引用的证据来源集合
        """
        llm_sources = set()

        if not reasoning:
            return llm_sources

        # 1. 提取URL（更宽松的正则）
        urls = re.findall(r'https?://[^\s\)\],]+', reasoning)
        llm_sources.update(urls)

        # 2. 提取引用的来源名称（扩展模式）
        citation_patterns = [
            # "According to X"
            r'[Aa]ccording to ([^,\.;]+)',
            # "X reported/stated/found..."
            r'([A-Z][a-zA-Z\s&\.]+(?:University|Institute|Bureau|Department|Bank|Agency|Organization|Commission|Post|Times|Journal|News|Guard|Press|Report|Survey|Index|Board))\s+(?:reported|stated|found|showed|indicated|confirmed|says|said)',
            # "Based on X"
            r'[Bb]ased on ([^,\.;]+(?:data|report|survey|study|analysis))',
            # "X's data/report"
            r"([A-Z][a-zA-Z\s&]+(?:University|Institute|Bureau|Department|Bank|Agency|Organization|Commission|Board))'s",
            # "The X report"
            r'[Tt]he ([A-Z][a-zA-Z\s&]+(?:Report|Survey|Index|Study))',
            # 支持缩写："According to FBI", "CDC data"
            r'[Aa]ccording to (?:the )?([A-Z]{2,})',
            r'([A-Z]{2,})\s+(?:data|report|survey|found|stated)',
        ]

        for pattern in citation_patterns:
            matches = re.findall(pattern, reasoning)
            for match in matches:
                clean_match = match.strip()
                if len(clean_match) > 2:  # 降低最小长度要求
                    llm_sources.add(clean_match)

        # 3. 提取数字和百分比（用于内容匹配）
        percentages = re.findall(r'\d+(?:\.\d+)?%', reasoning)
        llm_sources.update(percentages)

        # 提取较大的数字
        large_numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b', reasoning)
        llm_sources.update(large_numbers)

        return llm_sources

    @staticmethod
    def calculate_evidence_f1(ground_truth_sources: Set[str], predicted_sources: Set[str],
                             threshold: float = 0.2, debug: bool = False) -> Tuple[float, float, float, List[Tuple[str, str]]]:
        """
        计算证据匹配的Precision, Recall, F1

        参数：
            ground_truth_sources: 数据集中的evidence_sources（Ground Truth）
            predicted_sources: LLM在reasoning中引用的证据来源
            threshold: 模糊匹配阈值（降低到0.2，更容易匹配）
            debug: 是否返回匹配详情

        计算逻辑：
            1. 对于每个GT证据，遍历所有LLM引用的证据
            2. 如果找到匹配（通过模糊匹配），计数+1
            3. Precision = 匹配数 / LLM引用总数
            4. Recall = 匹配数 / GT证据总数
            5. F1 = 2 * P * R / (P + R)

        返回：(precision, recall, f1, matched_pairs)
        """
        # 特殊情况处理
        if not ground_truth_sources and not predicted_sources:
            return 1.0, 1.0, 1.0, []

        if not ground_truth_sources or not predicted_sources:
            return 0.0, 0.0, 0.0, []

        # 计算匹配
        matched = 0
        matched_pairs = []

        for gt_src in ground_truth_sources:
            for pred_src in predicted_sources:
                # 使用模糊匹配
                if EvidenceMatcher._fuzzy_match(gt_src, pred_src, threshold):
                    matched += 1
                    matched_pairs.append((gt_src, pred_src))
                    break  # 找到匹配后跳出内层循环

        # 计算指标
        precision = matched / len(predicted_sources) if predicted_sources else 0
        recall = matched / len(ground_truth_sources) if ground_truth_sources else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return precision, recall, f1, matched_pairs

    @staticmethod
    def _fuzzy_match(text1: str, text2: str, threshold: float = 0.2) -> bool:
        """
        模糊匹配两个文本（改进版，阈值降低到0.2）

        匹配策略：
        1. 包含关系：text1 in text2 或 text2 in text1
        2. 精确匹配：完全相同
        3. URL域名匹配：如果是URL，比较域名
        4. 词重叠：计算词的重叠比例 >= threshold

        参数：
            threshold: 词重叠阈值（默认0.2，即20%的词重叠就算匹配）
        """
        text1_lower = text1.lower()
        text2_lower = text2.lower()

        # 方法1: 包含关系
        if text1_lower in text2_lower or text2_lower in text1_lower:
            return True

        # 方法2: 精确匹配
        if text1 == text2:
            return True

        # 方法3: URL域名匹配
        if 'http' in text1 or 'http' in text2:
            domain1 = re.findall(r'https?://([^/]+)', text1)
            domain2 = re.findall(r'https?://([^/]+)', text2)
            if domain1 and domain2 and domain1[0] == domain2[0]:
                return True

        # 方法4: 词重叠
        words1 = set(re.findall(r'\w+', text1_lower))
        words2 = set(re.findall(r'\w+', text2_lower))

        # 过滤停用词（扩展列表）
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were',
            'according', 'reported', 'stated', 'said', 'based'
        }
        words1 = words1 - stopwords
        words2 = words2 - stopwords

        if not words1 or not words2:
            return False

        # 计算词重叠比例
        overlap = len(words1 & words2)
        min_len = min(len(words1), len(words2))

        return (overlap / min_len) >= threshold if min_len > 0 else False


class ExplanationEvaluator:
    """解释质量评估器"""

    def __init__(self, llm: QwenPlus):
        self.llm = llm

    def evaluate_explanation(self, claim: str, llm_reasoning: str, ground_truth_justification: str,
                           evidence_sources: List[Dict]) -> Dict:
        """
        评估LLM解释的正确性
        返回评估结果字典
        """

        # 构建评估prompt
        evidence_summary = "\n".join([
            f"- {ev.get('content', '')[:200]}..." for ev in evidence_sources[:3]
        ])

        prompt = f"""你是一个事实核查专家。请评估以下LLM生成的解释（reasoning）是否存在缺陷。

原始声明（Claim）:
{claim}

真实标注的解释（Ground Truth Justification）:
{ground_truth_justification}

可用证据来源:
{evidence_summary}

LLM生成的解释（LLM Reasoning）:
{llm_reasoning}

请仔细检查LLM的解释是否存在以下问题：
1. **逻辑错误**: 推理过程是否有逻辑漏洞或矛盾？
2. **虚构内容**: 是否编造了不存在的证据或事实？
3. **错误引用**: 是否错误引用或曲解了证据来源？
4. **事实错误**: 陈述的事实是否正确？与真实标注相符吗？
5. **知识错误**: 是否引入了错误的知识或概念？
6. **推理错误**: 从证据到结论的推理是否合理？

评分标准（0-100分）:
- 90-100: 完全正确，无任何缺陷
- 70-89: 基本正确，有轻微瑕疵
- 50-69: 部分正确，有明显问题
- 30-49: 严重错误，多处问题
- 0-29: 完全错误，严重虚构

请以JSON格式返回评估结果（不要使用markdown代码块）:
{{
    "score": 评分（0-100的整数）,
    "has_logical_errors": true/false,
    "has_fabrication": true/false,
    "has_wrong_citation": true/false,
    "has_factual_errors": true/false,
    "has_knowledge_errors": true/false,
    "has_reasoning_errors": true/false,
    "explanation": "简要说明存在的主要问题（2-3句话）"
}}
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.completion(messages, return_json=True, enable_search=False)

            result = json.loads(response)

            # 确保score在0-100之间
            result['score'] = max(0, min(100, result.get('score', 50)))

            return result

        except Exception as e:
            print(f"    ⚠️  解释评估失败: {e}")
            return {
                'score': 50,
                'has_logical_errors': False,
                'has_fabrication': False,
                'has_wrong_citation': False,
                'has_factual_errors': False,
                'has_knowledge_errors': False,
                'has_reasoning_errors': False,
                'explanation': f'评估失败: {str(e)}'
            }


class EnhancedLLMFactChecker:
    """增强版LLM事实核查评估器"""

    def __init__(self, api_key: str, dataset_path: str, enable_search: bool = True, debug_mode: bool = False):
        self.llm = QwenPlus(api_key)
        self.dataset = self.load_dataset(dataset_path)
        self.results = []
        self.enable_search = enable_search
        self.evidence_matcher = EvidenceMatcher()
        self.explanation_evaluator = ExplanationEvaluator(self.llm)
        self.debug_mode = debug_mode  # 是否打印详细debug信息

    def load_dataset(self, path: str) -> List[Dict]:
        """加载数据集"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_single_claim(self, item: Dict, index: int) -> Dict:
        """测试单个claim"""
        claim = item['claim']
        ground_truth_verdict = item['verdict']
        ground_truth_justification = item.get('justification', '')
        evidence_sources = item.get('evidence_sources', [])

        print(f"\n{'=' * 80}")
        print(f"[{index}] Claim: {claim[:100]}...")
        print(f"Ground Truth Verdict: {ground_truth_verdict}")

        try:
            # 改进的Prompt - 强制要求引用证据
            prompt = f"""You are a professional fact-checker with access to search capabilities. Use web search to verify the following claim.

Claim: "{claim}"

CRITICAL REQUIREMENTS - You MUST follow these instructions:
1. Search for relevant, credible information about this claim
2. Carefully analyze the claim based on search results
3. In your reasoning, you MUST cite specific sources using these formats:
   - "According to [Source Name]..."
   - "[Organization/Publication] reported that..."
   - Include URLs when available: (https://...)
   - Cite specific numbers, dates, and statistics with their sources

4. Provide your verdict as one of these exact terms:
   - "Supported" (if the claim is true based on evidence)
   - "Refuted" (if the claim is false based on evidence)
   - "Not Enough Evidence" (if you cannot find sufficient information)

5. Your reasoning should be 4-6 sentences with EXPLICIT source citations

GOOD EXAMPLE:
{{
  "verdict": "Supported",
  "reasoning": "According to the Federal Reserve Bank of St. Louis (https://fred.stlouisfed.org/series/UMCSENT), the University of Michigan Consumer Sentiment Index fell by 13% from December 2024. The Conference Board also reported a 17% decline in their Consumer Confidence Index since November 2024, as stated in their official release (https://www.conference-board.org/...). These official statistics from government and industry sources confirm the claim about declining consumer confidence.",
  "confidence": "High"
}}

BAD EXAMPLE (DO NOT DO THIS):
{{
  "verdict": "Supported",
  "reasoning": "Consumer confidence has declined significantly based on recent economic data.",
  "confidence": "Medium"
}}

Respond ONLY with a valid JSON object:
{{
  "verdict": "...",
  "reasoning": "...",
  "confidence": "..."
}}

Do not include any text outside the JSON object."""

            messages = [{"role": "user", "content": prompt}]

            print(f"  🔍 正在让LLM分析并搜索证据...")
            response = self.llm.completion(messages, return_json=True, enable_search=self.enable_search)

            # 解析响应
            try:
                response_json = json.loads(response)
                llm_verdict = response_json.get('verdict', 'Not Enough Evidence')
                llm_reasoning = response_json.get('reasoning', '')
                llm_confidence = response_json.get('confidence', 'Unknown')
            except json.JSONDecodeError:
                print(f"    ⚠️  JSON解析失败")
                llm_verdict = 'Not Enough Evidence'
                llm_reasoning = response
                llm_confidence = 'Low'

            print(f"  LLM Verdict: {llm_verdict}")
            print(f"  Confidence: {llm_confidence}")

            # 1. Verdict Accuracy
            verdict_match = (llm_verdict == ground_truth_verdict)
            print(f"  Verdict Match: {'✓' if verdict_match else '✗'}")

            # 2. Evidence Matching（改进版）
            print(f"\n  📊 评估证据匹配度...")

            # 提取Ground Truth证据（从数据集的evidence_sources字段）
            gt_evidence = self.evidence_matcher.extract_evidence_from_justification(
                ground_truth_justification, evidence_sources
            )

            # 提取LLM reasoning中引用的证据
            llm_evidence = self.evidence_matcher.extract_evidence_from_llm_reasoning(llm_reasoning)

            print(f"     Ground Truth证据数（数据集中的evidence_sources）: {len(gt_evidence)}")
            print(f"     LLM引用证据数（从reasoning中提取）: {len(llm_evidence)}")

            # Debug模式：显示详细证据
            if self.debug_mode:
                print(f"\n     【Ground Truth证据详情】")
                for i, ev in enumerate(gt_evidence, 1):
                    print(f"       {i}. {ev[:100]}...")

                print(f"\n     【LLM引用证据详情】")
                if llm_evidence:
                    for i, ev in enumerate(llm_evidence, 1):
                        print(f"       {i}. {ev}")
                else:
                    print(f"       ⚠️  LLM没有引用任何证据来源！")

            # 计算Evidence F1（使用降低的阈值0.2）
            ev_precision, ev_recall, ev_f1, matched_pairs = self.evidence_matcher.calculate_evidence_f1(
                gt_evidence, llm_evidence, threshold=0.2, debug=True
            )

            print(f"     Evidence Precision: {ev_precision:.3f} (匹配数/LLM引用数)")
            print(f"     Evidence Recall: {ev_recall:.3f} (匹配数/GT证据数)")
            print(f"     Evidence F1: {ev_f1:.3f}")

            # Debug模式：显示匹配详情
            if self.debug_mode and matched_pairs:
                print(f"\n     【匹配的证据对】")
                for i, (gt, llm) in enumerate(matched_pairs, 1):
                    print(f"       {i}. GT:  {gt[:80]}...")
                    print(f"          LLM: {llm[:80]}...")

            # 3. Explanation Correctness
            print(f"\n  🔍 评估解释正确性...")
            explanation_eval = self.explanation_evaluator.evaluate_explanation(
                claim, llm_reasoning, ground_truth_justification, evidence_sources
            )

            print(f"     Explanation Score: {explanation_eval['score']}/100")
            print(f"     主要问题: {explanation_eval.get('explanation', 'None')}")

            # 4. 计算综合Score
            # Score = 0.4 * Verdict_Acc + 0.3 * Evidence_F1 + 0.3 * (Explanation_Score/100)
            verdict_score = 1.0 if verdict_match else 0.0
            evidence_score = ev_f1
            explanation_score = explanation_eval['score'] / 100.0

            overall_score = (0.4 * verdict_score +
                           0.3 * evidence_score +
                           0.3 * explanation_score)

            print(f"\n  🎯 综合得分: {overall_score:.3f}")
            print(f"     = 0.4×{verdict_score:.2f} + 0.3×{evidence_score:.3f} + 0.3×{explanation_score:.3f}")

            return {
                'index': index,
                'claim': claim,
                'ground_truth_verdict': ground_truth_verdict,
                'ground_truth_justification': ground_truth_justification,
                'ground_truth_evidence_count': len(evidence_sources),
                'ground_truth_evidence': list(gt_evidence),  # 保存GT证据列表

                'llm_verdict': llm_verdict,
                'llm_reasoning': llm_reasoning,
                'llm_confidence': llm_confidence,
                'llm_evidence': list(llm_evidence),  # 保存LLM引用的证据列表

                # Metrics
                'verdict_match': verdict_match,
                'verdict_score': verdict_score,

                'evidence_precision': ev_precision,
                'evidence_recall': ev_recall,
                'evidence_f1': ev_f1,
                'evidence_score': evidence_score,
                'matched_evidence_pairs': [(gt[:100], llm[:100]) for gt, llm in matched_pairs],  # 保存匹配对

                'explanation_score': explanation_score,
                'explanation_eval': explanation_eval,

                'overall_score': overall_score,

                'success': True,
                'error': None,
                'original_data': item
            }

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'index': index,
                'claim': claim,
                'ground_truth_verdict': ground_truth_verdict,
                'success': False,
                'error': str(e),
                'original_data': item
            }

    def test_dataset(self, max_items: int = None, start_index: int = 0):
        """测试数据集"""
        print(f"{'=' * 80}")
        print(f"增强版LLM Fact-Checking 评估")
        print(f"{'=' * 80}")
        print(f"数据集大小: {len(self.dataset)}")
        print(f"LLM模型: Qwen-3")
        print(f"搜索功能: {'✅ 已开启' if self.enable_search else '❌ 未开启'}")
        print(f"Debug模式: {'✅ 已开启' if self.debug_mode else '❌ 未开启'}")

        test_items = self.dataset[start_index:start_index + max_items] if max_items else self.dataset[start_index:]
        print(f"测试数量: {len(test_items)}\n")

        for i, item in enumerate(test_items, start=start_index):
            result = self.test_single_claim(item, i)
            self.results.append(result)

            # 每5个暂停一下
            if (i - start_index + 1) % 5 == 0:
                print(f"\n⏸️  已处理 {i - start_index + 1}/{len(test_items)}，暂停3秒...")
                time.sleep(3)
            else:
                time.sleep(1)

        return self.results

    def calculate_metrics(self) -> Dict:
        """计算所有评估指标"""
        successful = [r for r in self.results if r['success']]

        if not successful:
            return {'error': '没有成功的测试'}

        total = len(successful)

        # 1. Verdict Accuracy
        verdict_accuracy = sum(r['verdict_match'] for r in successful) / total

        # 2. Evidence Macro-F1 (按verdict分组)
        by_verdict_evidence_f1 = defaultdict(list)
        for r in successful:
            verdict = r['ground_truth_verdict']
            by_verdict_evidence_f1[verdict].append(r['evidence_f1'])

        evidence_macro_f1_by_verdict = {
            verdict: sum(f1_list) / len(f1_list) if f1_list else 0.0
            for verdict, f1_list in by_verdict_evidence_f1.items()
        }

        # 整体Evidence Macro-F1 (所有verdict的平均)
        evidence_macro_f1 = sum(evidence_macro_f1_by_verdict.values()) / len(evidence_macro_f1_by_verdict) if evidence_macro_f1_by_verdict else 0.0

        # 3. Evidence Micro-F1 (全局)
        evidence_micro_f1 = sum(r['evidence_f1'] for r in successful) / total

        # 4. Explanation Correctness
        avg_explanation_score = sum(r['explanation_score'] for r in successful) / total

        # 统计各类错误
        error_types = {
            'logical_errors': sum(r['explanation_eval'].get('has_logical_errors', False) for r in successful),
            'fabrication': sum(r['explanation_eval'].get('has_fabrication', False) for r in successful),
            'wrong_citation': sum(r['explanation_eval'].get('has_wrong_citation', False) for r in successful),
            'factual_errors': sum(r['explanation_eval'].get('has_factual_errors', False) for r in successful),
            'knowledge_errors': sum(r['explanation_eval'].get('has_knowledge_errors', False) for r in successful),
            'reasoning_errors': sum(r['explanation_eval'].get('has_reasoning_errors', False) for r in successful)
        }

        # 5. Overall Score
        overall_score = sum(r['overall_score'] for r in successful) / total

        # Verdict分组准确率
        by_verdict_acc = defaultdict(lambda: {'total': 0, 'correct': 0})
        for r in successful:
            verdict = r['ground_truth_verdict']
            by_verdict_acc[verdict]['total'] += 1
            if r['verdict_match']:
                by_verdict_acc[verdict]['correct'] += 1

        verdict_accuracy_by_class = {
            verdict: stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0
            for verdict, stats in by_verdict_acc.items()
        }

        # 混淆矩阵
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        for r in successful:
            gt = r['ground_truth_verdict']
            pred = r['llm_verdict']
            confusion_matrix[gt][pred] += 1

        return {
            'total_tests': len(self.results),
            'successful_tests': total,
            'failed_tests': len(self.results) - total,

            # 主要指标
            'verdict_accuracy': verdict_accuracy,
            'evidence_macro_f1': evidence_macro_f1,
            'evidence_micro_f1': evidence_micro_f1,
            'explanation_correctness': avg_explanation_score,
            'overall_score': overall_score,

            # 详细指标
            'verdict_accuracy_by_class': verdict_accuracy_by_class,
            'evidence_macro_f1_by_verdict': evidence_macro_f1_by_verdict,
            'explanation_error_types': error_types,
            'confusion_matrix': {k: dict(v) for k, v in confusion_matrix.items()}
        }

    def print_report(self):
        """打印评估报告"""
        metrics = self.calculate_metrics()

        if 'error' in metrics:
            print(f"\n✗ 错误: {metrics['error']}")
            return

        print(f"\n{'=' * 80}")
        print(f"📊 增强版事实核查评估报告")
        print(f"{'=' * 80}")

        print(f"\n【基本信息】")
        print(f"  总测试数: {metrics['total_tests']}")
        print(f"  成功: {metrics['successful_tests']}")
        print(f"  失败: {metrics['failed_tests']}")

        print(f"\n{'=' * 80}")
        print(f"【核心指标】")
        print(f"{'=' * 80}")

        print(f"\n1️⃣  Verdict Accuracy (判决准确度)")
        print(f"   总体: {metrics['verdict_accuracy']:.2%}")
        print(f"   按类别:")
        for verdict, acc in metrics['verdict_accuracy_by_class'].items():
            print(f"     - {verdict}: {acc:.2%}")

        print(f"\n2️⃣  Evidence Macro-F1 (证据匹配-宏平均)")
        print(f"   总体: {metrics['evidence_macro_f1']:.3f}")
        print(f"   按判决类别:")
        for verdict, f1 in metrics['evidence_macro_f1_by_verdict'].items():
            print(f"     - {verdict}: {f1:.3f}")

        print(f"\n3️⃣  Evidence Micro-F1 (证据匹配-微平均)")
        print(f"   总体: {metrics['evidence_micro_f1']:.3f}")

        print(f"\n4️⃣  Explanation Correctness (解释正确性)")
        print(f"   平均得分: {metrics['explanation_correctness']:.2%}")
        print(f"   错误类型统计:")
        for error_type, count in metrics['explanation_error_types'].items():
            pct = count / metrics['successful_tests'] * 100
            print(f"     - {error_type}: {count} ({pct:.1f}%)")

        print(f"\n5️⃣  Overall Score (综合得分)")
        print(f"   综合得分: {metrics['overall_score']:.3f}")
        print(f"   计算公式: 0.4×Verdict_Acc + 0.3×Evidence_F1 + 0.3×Explanation")

        print(f"\n{'=' * 80}")
        print(f"【混淆矩阵】")
        print(f"{'=' * 80}")
        verdicts = ['Supported', 'Refuted', 'Not Enough Evidence']
        cm = metrics['confusion_matrix']

        # 表头
        print(f"   {'Ground Truth':<25} | ", end='')
        for v in verdicts:
            print(f"{v[:10]:>10} ", end='')
        print()
        print(f"   {'-' * 25}-+-{'-' * 35}")

        # 数据行
        for gt in verdicts:
            print(f"   {gt:<25} | ", end='')
            for pred in verdicts:
                count = cm.get(gt, {}).get(pred, 0)
                print(f"{count:>10} ", end='')
            print()

        print(f"\n{'=' * 80}")

    def save_results(self, output_path: str = 'enhanced_test_results.json'):
        """保存完整结果"""
        output = {
            'search_enabled': self.enable_search,
            'metrics': self.calculate_metrics(),
            'detailed_results': self.results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 完整结果已保存到: {output_path}")

    def save_error_analysis(self, output_path: str = 'error_analysis.json'):
        """保存错误分析"""
        errors = {
            'verdict_errors': [],
            'low_evidence_f1': [],
            'low_explanation_score': []
        }

        for r in self.results:
            if not r['success']:
                continue

            # Verdict错误
            if not r['verdict_match']:
                errors['verdict_errors'].append({
                    'index': r['index'],
                    'claim': r['claim'],
                    'ground_truth': r['ground_truth_verdict'],
                    'predicted': r['llm_verdict'],
                    'reasoning': r['llm_reasoning']
                })

            # Evidence F1低
            if r['evidence_f1'] < 0.3:
                errors['low_evidence_f1'].append({
                    'index': r['index'],
                    'claim': r['claim'],
                    'evidence_f1': r['evidence_f1'],
                    'ground_truth_evidence': r.get('ground_truth_evidence', []),
                    'llm_evidence': r.get('llm_evidence', []),
                    'matched_pairs': r.get('matched_evidence_pairs', []),
                    'ground_truth_justification': r['ground_truth_justification'],
                    'llm_reasoning': r['llm_reasoning']
                })

            # Explanation得分低
            if r['explanation_score'] < 0.5:
                errors['low_explanation_score'].append({
                    'index': r['index'],
                    'claim': r['claim'],
                    'explanation_score': r['explanation_score'],
                    'explanation_eval': r['explanation_eval'],
                    'llm_reasoning': r['llm_reasoning']
                })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

        print(f"✅ 错误分析已保存到: {output_path}")
        print(f"   - Verdict错误: {len(errors['verdict_errors'])} 条")
        print(f"   - Evidence F1低: {len(errors['low_evidence_f1'])} 条")
        print(f"   - Explanation得分低: {len(errors['low_explanation_score'])} 条")


def main():
    API_KEY = "sk-8faa7214041347609e67d5d09cec7266"
    DATASET_PATH = "../data/dataset_final.json"  # 修改为你的数据集路径

    # 创建增强版测试器
    tester = EnhancedLLMFactChecker(
        api_key=API_KEY,
        dataset_path=DATASET_PATH,
        enable_search=True,  # 开启搜索
        debug_mode=True      # 开启debug模式，显示详细证据匹配过程
    )

    # 测试数据集
    tester.test_dataset(max_items=1000, start_index=0)  # 先测试3条看效果

    # 打印报告
    tester.print_report()

    # 保存结果
    tester.save_results('enhanced_test_results_1_100.json')

    # 保存错误分析
    tester.save_error_analysis('error_analysis_1_100.json')


if __name__ == "__main__":
    main()