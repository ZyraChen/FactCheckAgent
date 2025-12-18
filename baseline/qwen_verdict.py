"""
简化版LLM Baseline测试脚本（修复版）
功能：
1. 检测 Verdict Accuracy（判决准确度）
2. 返回 LLM的判决理由（justification）
3. 返回 LLM搜索到的证据（evidence_sources）
4. 以结构化JSON格式保存

修复问题：
1. prompt和代码字段名不匹配（justification vs reasoning）
2. prompt的JSON格式错误
3. 添加对LLM返回的evidence_sources的处理
"""

import json
import time
import re
from typing import List, Dict, Set
from collections import defaultdict
import openai


class QwenPlus:
    """通义千问LLM（带搜索功能）"""

    def __init__(self, api_key):
        self.model = "qwen-plus-latest"
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
        """调用LLM completion"""
        response_format = {"type": "json_object"} if not enable_thinking and return_json else {"type": "text"}
        extra_body = {}

        if enable_search:
            extra_body = {
                "enable_thinking": enable_thinking,
                "enable_search": True,
                "search_options": {
                    "forced_search": True,
                    "search_strategy": "max"
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


class EvidenceExtractor:
    """证据提取器 - 从LLM的justification中提取引用的证据"""

    @staticmethod
    def extract_evidence_from_text(text: str) -> List[str]:
        """
        从文本中提取证据引用（作为备用方法）
        当LLM没有返回结构化的evidence_sources时使用
        """
        evidence_list = []

        if not text:
            return evidence_list

        # 1. 提取URL
        urls = re.findall(r'https?://[^\s\)\],]+', text)
        for url in urls:
            if url not in evidence_list:
                evidence_list.append(url)

        # 2. 提取引用的来源名称
        citation_patterns = [
            r'[Aa]ccording to ([^,\.;]+)',
            r'([A-Z][a-zA-Z\s&\.]+(?:University|Institute|Bureau|Department|Bank|Agency|Organization|Commission|Post|Times|Journal|News|Guard|Press|Report|Survey|Index|Board))\s+(?:reported|stated|found|showed|indicated|confirmed|says|said)',
            r'[Bb]ased on ([^,\.;]+(?:data|report|survey|study|analysis))',
            r"([A-Z][a-zA-Z\s&]+(?:University|Institute|Bureau|Department|Bank|Agency|Organization|Commission|Board))'s",
            r'[Tt]he ([A-Z][a-zA-Z\s&]+(?:Report|Survey|Index|Study))',
            r'[Aa]ccording to (?:the )?([A-Z]{2,})',
            r'([A-Z]{2,})\s+(?:data|report|survey|found|stated)',
        ]

        for pattern in citation_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_match = match.strip()
                if len(clean_match) > 2 and clean_match not in evidence_list:
                    evidence_list.append(clean_match)

        # 3. 提取关键数字和百分比
        percentages = re.findall(r'\d+(?:\.\d+)?%', text)
        for pct in percentages:
            if pct not in evidence_list:
                evidence_list.append(pct)

        return evidence_list


class VerdictTester:
    """Verdict准确度测试器（修复版）"""

    def __init__(self, api_key: str, dataset_path: str, enable_search: bool = True):
        self.llm = QwenPlus(api_key)
        self.dataset = self.load_dataset(dataset_path)
        self.results = []
        self.enable_search = enable_search
        self.evidence_extractor = EvidenceExtractor()

    def load_dataset(self, path: str) -> List[Dict]:
        """加载数据集"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_single_claim(self, item: Dict, index: int) -> Dict:
        """测试单个claim"""
        claim = item['claim']
        ground_truth_verdict = item['verdict']

        print(f"\n{'=' * 80}")
        print(f"[{index}] Claim: {claim[:100]}...")
        print(f"Ground Truth Verdict: {ground_truth_verdict}")

        try:
            # 修复后的prompt - 字段名统一，JSON格式正确
            prompt = f"""You are a professional fact-checker with access to search capabilities. Use web search to verify the following claim.

Claim: "{claim}"

CRITICAL REQUIREMENTS:
1. You must search for relevant, credible information about this claim
2. In your justification, you MUST cite specific sources:
   - You can use formats like: "According to [Source Name]..."
   - Include URLs in evidence sources
   - Mention the source organization/publication name
   - Cite specific numbers, dates, and statistics

3. Provide your verdict as one of these exact terms:
   - "Supported" (if the claim is true based on evidence)
   - "Refuted" (if the claim is false based on evidence)
   - "Not Enough Evidence" (if you cannot find sufficient information)

4. Provide a complete justification (4-6 sentences with explicit source citations)

5. Provide less than 5 evidence sources you actually used, including:
   - content: Primary content of the evidence
   - url: 
       - ONLY include URLs that you ACTUALLY found during your search. 
       - DO NOT fabricate, guess, or construct URLs
       - DO NOT use common patterns like "https://example.com/..."
       - ONLY use URLs that appeared in your search results
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
      "url": "Real URL",
      "credibility": "High" | "Medium" | "Low"
    }}
  ]
}}

Do not include any text outside the JSON object."""

            messages = [{"role": "user", "content": prompt}]

            print(f"  🔍 正在让LLM分析...")
            response = self.llm.completion(messages, return_json=True, enable_search=self.enable_search)

            # 打印原始响应（用于调试）
            print(f"\n  【原始响应】")
            print(f"  {response[:300]}...")

            # 解析响应 - 修复字段名
            try:
                response_json = json.loads(response)
                llm_verdict = response_json.get('verdict', 'Not Enough Evidence')
                llm_justification = response_json.get('justification', '')  # 修复：从justification获取
                llm_confidence = response_json.get('confidence', 'Unknown')
                llm_evidence_sources = response_json.get('evidence_sources', [])  # 新增：获取evidence_sources

                print(f"\n  【解析成功】")
                print(f"  - verdict: {llm_verdict}")
                print(f"  - justification长度: {len(llm_justification)} 字符")
                print(f"  - evidence_sources数量: {len(llm_evidence_sources)}")

            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON解析失败: {e}")
                print(f"    原始响应: {response[:500]}")
                llm_verdict = 'Not Enough Evidence'
                llm_justification = response
                llm_confidence = 'Low'
                llm_evidence_sources = []

            print(f"\n  LLM Verdict: {llm_verdict}")
            print(f"  Confidence: {llm_confidence}")

            # 判断verdict是否匹配
            verdict_match = (llm_verdict == ground_truth_verdict)
            print(f"  Verdict Match: {'✅ 正确' if verdict_match else '❌ 错误'}")

            if not verdict_match:
                print(f"    Expected: {ground_truth_verdict}")
                print(f"    Got: {llm_verdict}")

            # 显示LLM返回的证据来源
            if llm_evidence_sources:
                print(f"\n  📚 LLM提供的证据来源 ({len(llm_evidence_sources)}条):")
                for i, ev in enumerate(llm_evidence_sources[:3], 1):
                    content = ev.get('content', '')[:80]
                    url = ev.get('url', 'N/A')
                    cred = ev.get('credibility', 'Unknown')
                    print(f"    {i}. [{cred}] {content}...")
                    print(f"       URL: {url}")
            else:
                print(f"\n  ⚠️  LLM未返回结构化的evidence_sources")

                # 备用方案：从justification中提取证据
                extracted_evidence = self.evidence_extractor.extract_evidence_from_text(llm_justification)
                if extracted_evidence:
                    print(f"  🔍 从justification中提取到 {len(extracted_evidence)} 条证据引用:")
                    for i, ev in enumerate(extracted_evidence[:5], 1):
                        ev_display = ev[:80] + ('...' if len(ev) > 80 else '')
                        print(f"    {i}. {ev_display}")

            # 返回结构化结果
            return {
                'index': index,
                'claim': claim,

                # Ground Truth
                'ground_truth': {
                    'verdict': ground_truth_verdict,
                    'justification': item.get('justification', ''),
                    'evidence_sources': item.get('evidence_sources', [])
                },

                # LLM Response
                'llm_response': {
                    'verdict': llm_verdict,
                    'justification': llm_justification,  # 修复：使用justification
                    'confidence': llm_confidence,
                    'evidence_sources': llm_evidence_sources,  # 新增：LLM返回的证据来源
                },

                # Verdict评估
                'verdict_evaluation': {
                    'is_correct': verdict_match,
                    'expected': ground_truth_verdict,
                    'predicted': llm_verdict
                },

                'success': True,
                'error': None
            }

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'index': index,
                'claim': claim,
                'ground_truth': {
                    'verdict': ground_truth_verdict
                },
                'success': False,
                'error': str(e)
            }

    def test_dataset(self, max_items: int = None, start_index: int = 0):
        """测试数据集"""
        print(f"{'=' * 80}")
        print(f"Verdict准确度测试（修复版）")
        print(f"{'=' * 80}")
        print(f"数据集大小: {len(self.dataset)}")
        print(f"LLM模型: Qwen-Plus-Latest")
        print(f"搜索功能: {'✅ 已开启' if self.enable_search else '❌ 未开启'}")

        test_items = self.dataset[start_index:start_index + max_items] if max_items else self.dataset[start_index:]
        print(f"测试数量: {len(test_items)}\n")

        for i, item in enumerate(test_items, start=start_index):
            result = self.test_single_claim(item, i)
            self.results.append(result)

            # 每5个暂停一下，避免API限流
            if (i - start_index + 1) % 5 == 0:
                print(f"\n⏸️  已处理 {i - start_index + 1}/{len(test_items)}，暂停3秒...")
                time.sleep(3)
            else:
                time.sleep(1)

        return self.results

    def calculate_accuracy(self) -> Dict:
        """计算准确率统计"""
        successful = [r for r in self.results if r['success']]

        if not successful:
            return {'error': '没有成功的测试'}

        total = len(successful)
        correct = sum(1 for r in successful if r['verdict_evaluation']['is_correct'])
        accuracy = correct / total

        # 按verdict分类统计
        by_verdict = defaultdict(lambda: {'total': 0, 'correct': 0})
        for r in successful:
            gt_verdict = r['ground_truth']['verdict']
            by_verdict[gt_verdict]['total'] += 1
            if r['verdict_evaluation']['is_correct']:
                by_verdict[gt_verdict]['correct'] += 1

        accuracy_by_verdict = {
            verdict: {
                'accuracy': stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0,
                'correct': stats['correct'],
                'total': stats['total']
            }
            for verdict, stats in by_verdict.items()
        }

        # 混淆矩阵
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        for r in successful:
            gt = r['verdict_evaluation']['expected']
            pred = r['verdict_evaluation']['predicted']
            confusion_matrix[gt][pred] += 1

        return {
            'total_tests': len(self.results),
            'successful_tests': total,
            'failed_tests': len(self.results) - total,
            'overall_accuracy': accuracy,
            'correct_predictions': correct,
            'incorrect_predictions': total - correct,
            'accuracy_by_verdict': accuracy_by_verdict,
            'confusion_matrix': {k: dict(v) for k, v in confusion_matrix.items()}
        }

    def print_summary(self):
        """打印测试摘要"""
        metrics = self.calculate_accuracy()

        if 'error' in metrics:
            print(f"\n✗ 错误: {metrics['error']}")
            return

        print(f"\n{'=' * 80}")
        print(f"📊 Verdict准确度测试报告")
        print(f"{'=' * 80}")

        print(f"\n【基本信息】")
        print(f"  总测试数: {metrics['total_tests']}")
        print(f"  成功: {metrics['successful_tests']}")
        print(f"  失败: {metrics['failed_tests']}")

        print(f"\n【Verdict准确度】")
        print(f"  总体准确率: {metrics['overall_accuracy']:.2%}")
        print(f"  正确预测: {metrics['correct_predictions']}")
        print(f"  错误预测: {metrics['incorrect_predictions']}")

        print(f"\n【按Verdict类别统计】")
        for verdict, stats in metrics['accuracy_by_verdict'].items():
            print(f"  {verdict}:")
            print(f"    准确率: {stats['accuracy']:.2%}")
            print(f"    正确/总数: {stats['correct']}/{stats['total']}")

        print(f"\n【混淆矩阵】")
        verdicts = ['Supported', 'Refuted', 'Not Enough Evidence']
        cm = metrics['confusion_matrix']

        print(f"  {'Ground Truth':<25} | ", end='')
        for v in verdicts:
            print(f"{v[:10]:>10} ", end='')
        print()
        print(f"  {'-' * 25}-+-{'-' * 35}")

        for gt in verdicts:
            print(f"  {gt:<25} | ", end='')
            for pred in verdicts:
                count = cm.get(gt, {}).get(pred, 0)
                print(f"{count:>10} ", end='')
            print()

        print(f"\n{'=' * 80}")

    def save_results(self, output_path: str = 'verdict_test_results.json'):
        """保存完整结果为JSON格式"""
        output = {
            'metadata': {
                'model': 'qwen-plus-latest',
                'search_enabled': self.enable_search,
                'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_items': len(self.results)
            },
            'accuracy_metrics': self.calculate_accuracy(),
            'detailed_results': self.results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 结果已保存到: {output_path}")

        # 计算文件大小
        import os
        file_size = os.path.getsize(output_path) / 1024  # KB
        print(f"   文件大小: {file_size:.1f} KB")

    def save_verdict_errors(self, output_path: str = 'verdict_errors.json'):
        """保存判决错误的案例"""
        errors = []

        for r in self.results:
            if r['success'] and not r['verdict_evaluation']['is_correct']:
                errors.append({
                    'index': r['index'],
                    'claim': r['claim'],
                    'expected_verdict': r['verdict_evaluation']['expected'],
                    'predicted_verdict': r['verdict_evaluation']['predicted'],
                    'llm_justification': r['llm_response']['justification'],
                    'llm_confidence': r['llm_response']['confidence'],
                    'llm_evidence_sources': r['llm_response']['evidence_sources'],
                    'ground_truth_justification': r['ground_truth'].get('justification', ''),
                    'ground_truth_evidence_sources': r['ground_truth'].get('evidence_sources', [])
                })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

        print(f"✅ 判决错误案例已保存到: {output_path}")
        print(f"   共 {len(errors)} 个错误案例")


def main():
    # 配置
    API_KEY = "sk-8faa7214041347609e67d5d09cec7266"
    DATASET_PATH = "data/dataset_part_8.json"  # 修改为你的数据集路径

    # 创建测试器
    tester = VerdictTester(
        api_key=API_KEY,
        dataset_path=DATASET_PATH,
        enable_search=True  # 开启搜索
    )

    # 测试数据集
    print("开始测试...\n")
    tester.test_dataset(max_items=100, start_index=0)  # 先测试3条看效果

    # 打印摘要
    tester.print_summary()

    # 保存结果
    tester.save_results('qwen3_max_max/verdict_test_results_8.json')

    # 保存错误案例
    tester.save_verdict_errors('qwen3_max_max/verdict_errors_8.json')

    print("\n 测试完成！")


if __name__ == "__main__":
    main()