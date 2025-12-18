"""
Gemini 事实核查测试 - 正确的搜索工具版本

使用 google_search 工具（而不是 google_search_retrieval）
"""
import os

# 设置代理
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

import json
import time
from typing import List, Dict
from collections import defaultdict
import google.generativeai as genai
from google.generativeai import protos


class GeminiModelWithSearch:
    """Gemini LLM（正确的搜索工具）"""

    def __init__(self, api_key):
        self.model_name = "gemini-2.5-flash"
        genai.configure(api_key=api_key)

        print(f"初始化 Gemini 模型...")
        print(f"  模型: {self.model_name}")


        # # 定义Google搜索工具
        # grounding_tool = genai.types.Tool(
        #     google_search=genai.types.GoogleSearch()
        # )


        # 直接构建底层对象，绕过 SDK 的字符串检查
        tool_config = [
            protos.Tool(
                google_search={}
            )
        ]

        # 使用正确的搜索工具语法
        self.model = genai.GenerativeModel(
            self.model_name,
            tools=tool_config
        )

        print(f"已启用 google_search 工具\n")

        # 配置生成参数
        self.generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "max_output_tokens": 2048,
        }

    def completion(self, prompt: str) -> str:
        """调用 Gemini（自动使用搜索）"""
        try:
            print("  调用 Gemini (已启用搜索)...")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )

            return response.text

        except Exception as e:
            error_msg = str(e)

            # 处理配额错误
            if '429' in error_msg or 'quota' in error_msg.lower():
                print(f"   配额已用完！")
                print(f"   建议: 使用通义千问 API 代替")
                raise Exception("Gemini API 配额已用完")

            print(f"   API 调用错误: {error_msg}")
            raise


class LLMFactChecker:
    """事实核查器"""

    def __init__(self, api_key: str, dataset_path: str):
        print("=" * 70)
        print("初始化事实核查器（搜索版）")
        print("=" * 70 + "\n")

        self.llm = GeminiModelWithSearch(api_key)

        print(f"加载数据集: {dataset_path}")
        self.dataset = self.load_dataset(dataset_path)
        print(f"✓ 已加载 {len(self.dataset)} 条数据\n")

        self.results = []

    def load_dataset(self, path: str) -> List[Dict]:
        """加载数据集"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_single_claim(self, item: Dict, index: int) -> Dict:
        """测试单个 claim"""
        claim = item['claim']
        ground_truth = item['verdict']

        print(f"\n{'=' * 70}")
        print(f"[{index}] 测试中...")
        print(f"声明: {claim[:100]}...")
        print(f"真实标签: {ground_truth}")

        try:
            # 构建 prompt
            prompt = f"""You are a professional fact-checker with access to Google Search. 
Search the web to verify this claim:

Claim: "{claim}"

Instructions:
1. Use Google Search to find information
2. Analyze credible sources
3. Determine verdict: "Supported", "Refuted", or "Not Enough Evidence"
4. Cite sources in your reasoning
5. Rate confidence: High/Medium/Low

Respond with ONLY JSON (no markdown):
{{
  "verdict": "Supported",
  "reasoning": "Brief explanation with sources",
  "confidence": "High"
}}"""

            print(f"  调用 Gemini...")
            start_time = time.time()

            response = self.llm.completion(prompt)

            elapsed = time.time() - start_time
            print(f"  ✓ 用时: {elapsed:.1f}秒")

            # 解析响应
            try:
                cleaned = response.strip()
                if '```json' in cleaned:
                    cleaned = cleaned.split('```json')[1].split('```')[0]
                elif '```' in cleaned:
                    cleaned = cleaned.split('```')[1].split('```')[0]
                cleaned = cleaned.strip()

                result_json = json.loads(cleaned)
                llm_verdict = result_json.get('verdict', 'Not Enough Evidence')
                reasoning = result_json.get('reasoning', '')
                confidence = result_json.get('confidence', 'Unknown')

            except:
                if 'Supported' in response:
                    llm_verdict = 'Supported'
                elif 'Refuted' in response:
                    llm_verdict = 'Refuted'
                else:
                    llm_verdict = 'Not Enough Evidence'
                reasoning = response[:300]
                confidence = 'Low'

            print(f"  LLM: {llm_verdict} | 真实: {ground_truth}")
            match = (llm_verdict == ground_truth)
            print(f"  {'✓ 正确' if match else '✗ 错误'}")

            return {
                'index': index,
                'claim': claim,
                'ground_truth': ground_truth,
                'llm_verdict': llm_verdict,
                'llm_reasoning': reasoning,
                'llm_confidence': confidence,
                'match': match,
                'success': True,
                'time': elapsed,
                'original_data': item
            }

        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ 错误: {error_msg}")

            # 如果是配额错误，停止测试
            if 'quota' in error_msg.lower() or '配额' in error_msg:
                print(f"\n Gemini 配额已用完，无法继续测试")
                raise

            return {
                'index': index,
                'claim': claim,
                'ground_truth': ground_truth,
                'success': False,
                'error': error_msg,
                'original_data': item
            }

    def test_dataset(self, max_items: int = None, start_index: int = 0):
        """测试数据集"""
        print(f"\n{'=' * 70}")
        print(f"开始批量测试")
        print(f"{'=' * 70}")

        test_items = self.dataset[start_index:start_index + max_items] if max_items else self.dataset[start_index:]
        print(f"将测试 {len(test_items)} 条数据\n")

        total_time = 0
        success_count = 0

        for i, item in enumerate(test_items, start=start_index):
            try:
                result = self.test_single_claim(item, i)
                self.results.append(result)

                if result['success']:
                    success_count += 1
                    total_time += result.get('time', 0)

                    processed = i - start_index + 1
                    if success_count > 0:
                        avg_time = total_time / success_count
                        remaining_items = len(test_items) - processed
                        estimated_remaining = remaining_items * avg_time

                        print(f"\n  进度: {processed}/{len(test_items)}")
                        print(f"   平均: {avg_time:.1f}秒/条 | 预计剩余: {estimated_remaining/60:.1f}分钟")

                # 暂停避免超过配额限制
                time.sleep(2)

            except Exception as e:
                if 'quota' in str(e).lower() or '配额' in str(e):
                    print(f"\n遇到配额限制，停止测试")
                    break

        print(f"\n{'=' * 70}")
        print(f"测试完成: {success_count}/{len(test_items)} 成功")
        print(f"{'=' * 70}")

        return self.results

    def calculate_accuracy(self) -> Dict:
        """计算准确率"""
        successful = [r for r in self.results if r['success'] and 'match' in r]
        if not successful:
            return {'error': '没有成功的测试'}

        total = len(successful)
        correct = sum(1 for r in successful if r['match'])
        accuracy = correct / total

        by_verdict = defaultdict(lambda: {'total': 0, 'correct': 0})
        for r in successful:
            gt = r['ground_truth']
            by_verdict[gt]['total'] += 1
            if r['match']:
                by_verdict[gt]['correct'] += 1

        confusion_matrix = defaultdict(lambda: defaultdict(int))
        for r in successful:
            confusion_matrix[r['ground_truth']][r['llm_verdict']] += 1

        return {
            'total_tests': len(self.results),
            'successful_tests': total,
            'failed_tests': len(self.results) - total,
            'overall_accuracy': accuracy,
            'correct_predictions': correct,
            'by_verdict': dict(by_verdict),
            'confusion_matrix': {k: dict(v) for k, v in confusion_matrix.items()}
        }

    def print_report(self):
        """打印报告"""
        metrics = self.calculate_accuracy()
        if 'error' in metrics:
            print(f"\n✗ {metrics['error']}")
            return

        print(f"\n{'=' * 70}")
        print(f"测试报告")
        print(f"{'=' * 70}")
        print(f"\n总体准确率: {metrics['overall_accuracy']:.2%}")
        print(f"   ({metrics['correct_predictions']}/{metrics['successful_tests']})")

        print(f"\n按类别:")
        for verdict, stats in metrics['by_verdict'].items():
            acc = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
            print(f"  {verdict:25s}: {acc:.2%} ({stats['correct']}/{stats['total']})")

    def save_results(self, output_path: str = 'gemini_results.json'):
        """保存结果"""
        output = {
            'model': 'gemini-2.5-flash-exp',
            'search_enabled': True,
            'metrics': self.calculate_accuracy(),
            'results': self.results
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 结果已保存: {output_path}")

    def save_wrong_predictions(self, output_path: str = 'gemini_wrong.json'):
        """保存错误预测"""
        wrong = [r['original_data'] for r in self.results
                if r['success'] and 'match' in r and not r['match']]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(wrong, f, ensure_ascii=False, indent=2)
        print(f"✓ 错误数据已保存: {output_path} ({len(wrong)} 条)")


def main():
    """主函数"""

    print("\n" + "=" * 70)
    print("Gemini 事实核查测试 - 搜索版本")
    print("=" * 70 + "\n")

    API_KEY = "AIzaSyBZRx1LHYBWVSCNTZ94n_pxzrYfN4HNGsA"
    DATASET_PATH = "dataset_1_300/claim_v4.json"


    try:
        tester = LLMFactChecker(
            api_key=API_KEY,
            dataset_path=DATASET_PATH
        )

        tester.test_dataset(max_items=100, start_index=0)

        tester.print_report()
        tester.save_results('gemini_results_v4.json')
        tester.save_wrong_predictions('gemini_wrong_v4.json')

        print("\n 完成！")

    except Exception as e:
        print(f"\n错误: {e}")

        if 'quota' in str(e).lower() or '配额' in str(e):
            print(f"\nGemini 配额已用完")


if __name__ == "__main__":
    main()