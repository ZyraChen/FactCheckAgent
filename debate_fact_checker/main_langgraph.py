"""
主程序 - 使用LangGraph框架
"""
import os
os.environ["JINA_API_KEY"] = "jina_518b9cb292b249139bedce5123349109HnqXMjmaY94laLNX3J50eXfmd9E5"

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 改进:使用证据节点架构的workflow
sys.path.insert(0, '/mnt/user-data/outputs')
from graph.langgraph_workflow import run_langgraph_debate
from utils.models import ClaimData
import config


def process_single_claim(claim: str, rounds: int = 3):
    """处理单个claim"""
    result = run_langgraph_debate(claim, max_rounds=rounds)

    # 保存结果
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # 保存论辩图
    with open(output_dir / "argumentation_graph.json", "w", encoding="utf-8") as f:
        json.dump(result["arg_graph_data"], f, ensure_ascii=False, indent=2, default=str)

    # 保存判决
    with open(output_dir / "verdict.json", "w", encoding="utf-8") as f:
        json.dump(result["verdict"], f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✓ 结果已保存到output/目录")

    return result


def process_dataset(dataset_path: str, output_path: str, max_samples: int = None):
    """批量处理数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if max_samples:
        dataset = dataset[:max_samples]

    print(f"加载了 {len(dataset)} 条数据\n")

    results = []

    for i, item in enumerate(dataset):
        print(f"\n{'#'*70}")
        print(f"处理第 {i+1}/{len(dataset)} 条")
        print(f"{'#'*70}")

        try:
            result = run_langgraph_debate(item["claim"], max_rounds=3)

            results.append({
                "claim": item["claim"],
                "predicted": result["verdict"].get("decision"),
                "ground_truth": item.get("verdict"),
                "confidence": result["verdict"].get("confidence"),
                "correct": result["verdict"].get("decision") == item.get("verdict")
            })

            # 保存中间结果
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 统计
    correct = sum(1 for r in results if r.get("correct"))
    total = len([r for r in results if r.get("correct") is not None])
    accuracy = correct / total if total > 0 else 0

    print(f"\n\n{'='*70}")
    print(f"评估完成")
    print(f"{'='*70}")
    print(f"总数: {total}")
    print(f"正确: {correct}")
    print(f"准确率: {accuracy:.2%}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LangGraph双Agent辩论式事实核查")
    parser.add_argument("--claim", type=str, help="单个claim")
    parser.add_argument("--dataset", type=str,  default="data/dataset_part_1.json")
    parser.add_argument("--output", type=str, default="output/results.json")
    parser.add_argument("--max-samples", type=int, default=1)
    parser.add_argument("--rounds", type=int, default=3, help="辩论轮次")

    args = parser.parse_args()

    if args.claim:
        process_single_claim(args.claim, args.rounds)
    elif args.dataset:
        process_dataset(args.dataset, args.output, args.max_samples)
    else:
        # 默认测试
        test_claim = "尼日利亚每年新增HIV感染接近20万。"
        process_single_claim(test_claim, rounds=2)