"""
简化版LLM Baseline测试脚本（支持断点续传版）
功能：
1. 检测 Verdict Accuracy（判决准确度）
2. 返回 LLM的判决理由（justification）
3. 返回 LLM搜索到的证据（evidence_sources）
4. 以结构化JSON格式保存
5. 支持断点续传 - 终端后可从上次位置继续
6. 实时保存日志和结果

新增功能：
- 每处理1条就保存一次结果
- 支持从中断位置继续执行
- 实时保存进度文件
"""

import json
import time
import re
import os
from typing import List, Dict, Set
from collections import defaultdict
from datetime import datetime

# 禁用所有代理，确保直连阿里云服务器
os.environ['NO_PROXY'] = 'dashscope.aliyuncs.com'
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
import dashscope
import openai


class QwenPlus:
    """通义千问LLM（带搜索功能）"""

    def __init__(self, api_key):
        self.model = "qwen-plus-2025-12-01"
        self.llm = openai.OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    def _cons_kwargs(self, messages: list[dict]) -> dict:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "timeout": 20,
        }
        return kwargs

    def completion(self, messages: list[dict], enable_thinking=False, return_json=False, enable_search=False, return_full_response=False):
        """调用LLM completion

        Args:
            return_full_response: 如果为True，返回完整响应对象（包含搜索引用）；否则只返回文本内容
        """

        try:
            # response_format = {"type": "json_object"} if not enable_thinking and return_json else {"type": "text"}
            # extra_body = {}
            #
            # if enable_search:
            #     extra_body = {
            #         "enable_thinking": False,
            #         "enable_search": True,
            #         "search_options": {
            #             "forced_search": True,
            #             "search_strategy": "max"
            #         }
            #     }
            #
            # rsp = self.llm.chat.completions.create(
            #         **self._cons_kwargs(messages),
            #         extra_body=extra_body if enable_search else None,
            #         response_format=response_format
            # )
            rsp = dashscope.Generation.call(
                api_key=self.llm.api_key,
                model="qwen-plus-2025-12-01",
                messages=messages,
                enable_search=True,
                temperature=0.1,
                search_options={
                    "enable_source": True,
                    "forced_search": True,
                    "search_strategy": "max"
                },
                result_format="message"
            )
            for web in rsp.output.search_info["search_results"]:
                print(f"[{web['index']}]: {web['title']}")
                print(f"URL: {web['url']}")
                print(f"网站: {web['site_name']}\n")

        except openai.RateLimitError as e:
            print("    API请求超过限制，等待10秒...")
            time.sleep(10)
            return self.completion(messages, enable_thinking, return_json, enable_search, return_full_response)
        except openai.APITimeoutError as e:
            print("    API请求超时，等待10秒...")
            time.sleep(10)
            return self.completion(messages, enable_thinking, return_json, enable_search, return_full_response)

        return rsp.output.choices[0].message.content, rsp.output.search_info["search_results"]


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
    """Verdict准确度测试器（支持断点续传版）"""

    def __init__(self, api_key: str, dataset_path: str, output_dir: str = 'output', enable_search: bool = True):
        self.llm = QwenPlus(api_key)
        self.dataset = self.load_dataset(dataset_path)
        self.results = []
        self.enable_search = enable_search
        self.evidence_extractor = EvidenceExtractor()

        # 输出目录
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 关键文件路径
        self.progress_file = os.path.join(output_dir, 'progress.json')
        self.results_file = os.path.join(output_dir, 'results.json')
        self.log_file = os.path.join(output_dir, 'test.log')

        # 加载已有进度
        self.load_progress()

    def load_dataset(self, path: str) -> List[Dict]:
        """加载数据集"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_progress(self):
        """加载已有进度"""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                self.processed_indices = set(progress.get('processed_indices', []))
                print(f" 已加载进度文件，已处理 {len(self.processed_indices)} 条")
        else:
            self.processed_indices = set()
            print(" 未找到进度文件，从头开始")

        # 加载已有结果
        if os.path.exists(self.results_file):
            with open(self.results_file, 'r', encoding='utf-8') as f:
                self.results = json.load(f)
                print(f" 已加载 {len(self.results)} 条已有结果")

    def save_progress(self):
        """保存进度"""
        progress = {
            'processed_indices': list(self.processed_indices),
            'total_processed': len(self.processed_indices),
            'last_update': datetime.now().isoformat()
        }

        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def save_results(self):
        """实时保存结果"""
        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    def log(self, message: str):
        """写入日志文件"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"

        # 同时打印到控制台和写入文件
        print(message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)

    def test_single_claim(self, item: Dict, index: int) -> Dict:
        """测试单个claim"""
        claim = item['claim']
        ground_truth_verdict = item['verdict']

        self.log(f"\n{'=' * 80}")
        self.log(f"[{index}] Claim: {claim[:100]}...")
        self.log(f"Ground Truth Verdict: {ground_truth_verdict}")

        try:
            # 使用你的baseline prompt
            prompt = f"""Use web search to verify the claim below.

Claim: "{claim}"

Requirements:
1. Search for relevant information
2. Provide up to 5 evidence sources with: content, URL (from actual search results only), and credibility level (High/Medium/Low)
3. Make a verdict: 
    - Supported: The claim is TRUE based on the evidence you found
    - Refuted: The claim is FALSE based on the evidence you found
    - Not Enough Evidence: Insufficient reliable information to determine truth or falsehood, the issue involves unresolved academic/expert controversy, or credible sources provide irreconcilable conflicting information.
4. Write 4-6 sentences justification citing your sources

Respond in JSON format with fields: claim, verdict, justification, confidence, evidence_sources.
The response language must match the claim language."""

            messages = [
                {
                    "role": "system",
                    "content": """You are a professional fact-checker. Always verify claims using web search and provide accurate, well-cited analysis."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            self.log(f"  正在让LLM分析...")
            response, evidence = self.llm.completion(messages, return_json=True, enable_search=self.enable_search)

            json_evidence = []

            # 解析响应
            try:
                response_json = json.loads(response)
                llm_verdict = response_json.get('verdict', 'Not Enough Evidence')
                llm_justification = response_json.get('justification', '')
                llm_confidence = response_json.get('confidence', 'Unknown')

                for web in evidence:
                    json_evidence.append({
                        "title": web["title"],
                        "url": web["url"],
                        "site_name": web["site_name"]
                    })

                self.log(f"\n  【解析成功】")
                self.log(f"  - verdict: {llm_verdict}")
                self.log(f"  - justification长度: {len(llm_justification)} 字符")
                self.log(f"  - evidence_sources数量: {len(json_evidence)}")

            except json.JSONDecodeError as e:
                self.log(f"      JSON解析失败: {e}")
                self.log(f"    原始响应: {response[:500]}")
                llm_verdict = 'Not Enough Evidence'
                llm_justification = response
                llm_confidence = 'Low'
                json_evidence = []

            self.log(f"\n  LLM Verdict: {llm_verdict}")
            self.log(f"  Confidence: {llm_confidence}")

            # 判断verdict是否匹配
            verdict_match = (llm_verdict == ground_truth_verdict)
            self.log(f"  Verdict Match: {' 正确' if verdict_match else ' 错误'}")

            if not verdict_match:
                self.log(f"    Expected: {ground_truth_verdict}")
                self.log(f"    Got: {llm_verdict}")

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
                    'justification': llm_justification,
                    'confidence': llm_confidence,
                    'evidence_sources': json_evidence,
                },

                # Verdict评估
                'verdict_evaluation': {
                    'is_correct': verdict_match,
                    'expected': ground_truth_verdict,
                    'predicted': llm_verdict
                },

                'success': True,
                'error': None,
                'processed_at': datetime.now().isoformat()
            }

        except Exception as e:
            self.log(f"  ✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'index': index,
                'claim': claim,
                'ground_truth': {
                    'verdict': ground_truth_verdict
                },
                'success': False,
                'error': str(e),
                'processed_at': datetime.now().isoformat()
            }

    def test_dataset(self, max_items: int = None, start_index: int = 0):
        """测试数据集（支持断点续传）"""
        self.log(f"{'=' * 80}")
        self.log(f"Verdict准确度测试")
        self.log(f"{'=' * 80}")
        self.log(f"数据集大小: {len(self.dataset)}")
        self.log(f"LLM模型: Qwen-plus-2025-12-01")
        self.log(f"search_strategy: max")
        self.log(f"搜索功能: {' 已开启' if self.enable_search else ' 未开启'}")
        self.log(f"强制搜索: 已开启")
        self.log(f"温度: 0.1")
        test_items = self.dataset[start_index:start_index + max_items] if max_items else self.dataset[start_index:]
        self.log(f"测试范围: {start_index} - {start_index + len(test_items)}")
        self.log(f"已处理: {len(self.processed_indices)} 条")
        self.log(f"待处理: {len([i for i in range(start_index, start_index + len(test_items)) if i not in self.processed_indices])} 条\n")

        for i, item in enumerate(test_items, start=start_index):
            # 跳过已处理的
            if i in self.processed_indices:
                self.log(f"  [{i}] 已处理，跳过")
                continue

            # 处理当前item
            result = self.test_single_claim(item, i)
            self.results.append(result)

            # 标记为已处理
            self.processed_indices.add(i)

            # 立即保存进度和结果
            self.save_progress()
            self.save_results()
            self.log(f"已保存进度 ({len(self.processed_indices)}/{len(test_items)})")

            # 每5个暂停一下，避免API限流
            if (len(self.processed_indices)) % 5 == 0:
                self.log(f"\n 已处理 {len(self.processed_indices)}/{len(test_items)}，暂停3秒...")
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
            self.log(f"\n✗ 错误: {metrics['error']}")
            return

        self.log(f"\n{'=' * 80}")
        self.log(f" Verdict准确度测试报告")
        self.log(f"{'=' * 80}")

        self.log(f"\n【基本信息】")
        self.log(f"  总测试数: {metrics['total_tests']}")
        self.log(f"  成功: {metrics['successful_tests']}")
        self.log(f"  失败: {metrics['failed_tests']}")

        self.log(f"\n【Verdict准确度】")
        self.log(f"  总体准确率: {metrics['overall_accuracy']:.2%}")
        self.log(f"  正确预测: {metrics['correct_predictions']}")
        self.log(f"  错误预测: {metrics['incorrect_predictions']}")

        self.log(f"\n【按Verdict类别统计】")
        for verdict, stats in metrics['accuracy_by_verdict'].items():
            self.log(f"  {verdict}:")
            self.log(f"    准确率: {stats['accuracy']:.2%}")
            self.log(f"    正确/总数: {stats['correct']}/{stats['total']}")

        self.log(f"\n【混淆矩阵】")
        verdicts = ['Supported', 'Refuted', 'Not Enough Evidence']
        cm = metrics['confusion_matrix']

        header = f"  {'Ground Truth':<25} | "
        for v in verdicts:
            header += f"{v[:10]:>10} "
        self.log(header)
        self.log(f"  {'-' * 25}-+-{'-' * 35}")

        for gt in verdicts:
            row = f"  {gt:<25} | "
            for pred in verdicts:
                count = cm.get(gt, {}).get(pred, 0)
                row += f"{count:>10} "
            self.log(row)

        self.log(f"\n{'=' * 80}")

    def save_final_report(self, output_path: str = None):
        """保存最终报告"""
        if output_path is None:
            output_path = os.path.join(self.output_dir, 'final_report.json')

        output = {
            'metadata': {
                'model': 'qwen-plus-2025-12-01',
                'search_enabled': self.enable_search,
                'test_start': min([r.get('processed_at', '') for r in self.results]) if self.results else None,
                'test_end': max([r.get('processed_at', '') for r in self.results]) if self.results else None,
                'total_items': len(self.results)
            },
            'accuracy_metrics': self.calculate_accuracy(),
            'detailed_results': self.results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        self.log(f"\n 最终报告已保存到: {output_path}")

        # 计算文件大小
        file_size = os.path.getsize(output_path) / 1024  # KB
        self.log(f"   文件大小: {file_size:.1f} KB")

    def save_verdict_errors(self, output_path: str = None):
        """保存判决错误的案例"""
        if output_path is None:
            output_path = os.path.join(self.output_dir, 'verdict_errors.json')

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

        self.log(f" 判决错误案例已保存到: {output_path}")
        self.log(f"   共 {len(errors)} 个错误案例")


def main():
    # 配置
    API_KEY = "sk-cfa241b1db8e434bb20a31ee29202121"
    DATASET_PATH = "../data/dataset_latest.json"
    OUTPUT_DIR = "qwen_plus_baseline_output"

    # 创建测试器
    tester = VerdictTester(
        api_key=API_KEY,
        dataset_path=DATASET_PATH,
        output_dir=OUTPUT_DIR,
        enable_search=True
    )

    # 测试数据集（支持断点续传）
    print("开始测试（支持断点续传）...\n")
    try:
        tester.test_dataset(max_items=1000, start_index=0)
    except KeyboardInterrupt:
        print("\n\n  检测到中断信号（Ctrl+C）")
        print(" 正在保存当前进度...")
        tester.save_progress()
        tester.save_results()
        print(" 进度已保存，下次运行将从中断处继续")
        return

    # 打印摘要
    tester.print_summary()

    # 保存最终报告
    tester.save_final_report()

    # 保存错误案例
    tester.save_verdict_errors()

    print("\n 测试完成！")
    print(f" 所有文件已保存到: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()