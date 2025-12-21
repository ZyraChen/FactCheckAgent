"""
主程序 - LangChain Lite 版本

使用 LangChain Chain 组织 LLM 调用，完全保留原始 workflow
"""

import os
os.environ["JINA_API_KEY"] = "jina_518b9cb292b249139bedce5123349109HnqXMjmaY94laLNX3J50eXfmd9E5"

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from workflow.debate_workflow_lc import run_debate_workflow_lc
import config


def process_single_claim(claim: str, rounds: int = 3, ground_truth: str = None):
    """
    处理单个claim

    Args:
        claim: 要核查的claim
        rounds: 辩论轮次
        ground_truth: 数据集中的真实标签（可选）

    Returns:
        判决结果
    """
    print(f"\n{'='*80}")
    print(f"LangChain Lite 事实核查系统")
    print(f"（保留原始 workflow，仅用 Chain 组织 LLM 调用）")
    print(f"{'='*80}\n")
    print(f"Claim: {claim}\n")

    result = run_debate_workflow_lc(claim, max_rounds=rounds)

    # 设置 ground_truth
    if ground_truth:
        result["complete_log"]["ground_truth"] = ground_truth
        result["complete_log"]["evaluation"]["ground_truth"] = ground_truth
        result["complete_log"]["evaluation"]["correct"] = (
            result["verdict"]["decision"] == ground_truth
        )

    # 保存结果
    output_dir = Path("output/output_1_1")
    output_dir.mkdir(exist_ok=True)

    # 保存论辩图
    with open(output_dir / "argumentation_graph_lc_lite.json", "w", encoding="utf-8") as f:
        json.dump(result["arg_graph_data"], f, ensure_ascii=False, indent=2, default=str)

    # 保存判决
    with open(output_dir / "verdict_lc_lite.json", "w", encoding="utf-8") as f:
        json.dump(result["verdict"], f, ensure_ascii=False, indent=2, default=str)

    # 保存完整日志
    with open(output_dir / "complete_log.json", "w", encoding="utf-8") as f:
        json.dump(result["complete_log"], f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✓ 结果已保存到 output/ 目录")
    print(f"  - argumentation_graph_lc_lite.json")
    print(f"  - verdict_lc_lite.json")
    print(f"  - complete_log.json")

    return result


def process_dataset(dataset_path: str, output_path: str, max_samples: int = None):
    """
    批量处理数据集（支持断点续传）

    Args:
        dataset_path: 数据集路径
        output_path: 输出路径
        max_samples: 最大处理数量

    Returns:
        结果列表
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if max_samples:
        dataset = dataset[:max_samples]

    print(f"加载了 {len(dataset)} 条数据\n")

    # 创建日志目录
    output_dir = Path("output/output_1_1")
    output_dir.mkdir(exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # 进度文件路径
    progress_file = output_dir / "progress.json"

    # 尝试加载已有结果和进度
    results = []
    processed_indices = set()

    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
                processed_indices = set(progress_data.get("processed_indices", []))
                print(f"检测到进度文件，已处理 {len(processed_indices)} 条数据")
                print(f"   将从第 {len(processed_indices)+1} 条继续...\n")
        except Exception as e:
            print(f"⚠ 无法读取进度文件: {e}")

    # 加载已有结果
    if Path(output_path).exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
                print(f"📂 加载了 {len(results)} 条已有结果\n")
        except Exception as e:
            print(f"⚠ 无法读取结果文件: {e}")
            results = []

    for i, item in enumerate(dataset):
        # 跳过已处理的数据
        if i in processed_indices:
            print(f"⏭️  跳过第 {i+1}/{len(dataset)} 条（已处理）")
            continue

        print(f"\n{'#'*70}")
        print(f"处理第 {i+1}/{len(dataset)} 条")
        print(f"{'#'*70}")

        try:
            result = run_debate_workflow_lc(item["claim"], max_rounds=3)

            ground_truth = item.get("verdict")

            # 设置 ground_truth 到 complete_log
            if ground_truth:
                result["complete_log"]["ground_truth"] = ground_truth
                result["complete_log"]["evaluation"]["ground_truth"] = ground_truth
                result["complete_log"]["evaluation"]["correct"] = (
                    result["verdict"]["decision"] == ground_truth
                )

            # 保存单个 claim 的完整日志
            log_filename = f"log_{i+1:03d}.json"
            with open(logs_dir / log_filename, "w", encoding="utf-8") as f:
                json.dump(result["complete_log"], f, ensure_ascii=False, indent=2, default=str)

            results.append({
                "index": i,
                "claim": item["claim"],
                "predicted": result["verdict"].get("decision"),
                "ground_truth": ground_truth,
                "confidence": result["verdict"].get("confidence"),
                "correct": result["verdict"].get("decision") == ground_truth
            })

            # 立即保存结果摘要
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # 更新进度文件
            processed_indices.add(i)
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump({
                    "processed_indices": sorted(list(processed_indices)),
                    "total": len(dataset),
                    "last_updated": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)

            print(f"✓ 完整日志已保存: {log_filename}")
            print(f"✓ 进度已更新: {len(processed_indices)}/{len(dataset)}")

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

            # 即使出错也保存一条错误记录
            results.append({
                "index": i,
                "claim": item["claim"],
                "predicted": None,
                "ground_truth": item.get("verdict"),
                "confidence": None,
                "correct": None,
                "error": str(e)
            })

            # 保存结果和进度
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            processed_indices.add(i)
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump({
                    "processed_indices": sorted(list(processed_indices)),
                    "total": len(dataset),
                    "last_updated": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)

            continue

    # 统计（只统计成功的）
    valid_results = [r for r in results if r.get("predicted") is not None]
    correct = sum(1 for r in valid_results if r.get("correct"))
    total = len([r for r in valid_results if r.get("correct") is not None])
    accuracy = correct / total if total > 0 else 0

    print(f"\n\n{'='*70}")
    print(f"评估完成")
    print(f"{'='*70}")
    print(f"总数: {total}")
    print(f"正确: {correct}")
    print(f"准确率: {accuracy:.2%}")

    # 保存统计
    stats = {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "processed": len(processed_indices),
        "failed": len(results) - total,
        "results": results
    }

    with open(output_path.replace('.json', '_stats.json'), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LangChain Lite 辩论式事实核查")
    # parser.add_argument("--claim", type=str, default="越南通过人工智能法,在最后立法会议中通过51项法案")
    parser.add_argument("--dataset", type=str, default="../data/dataset_part_8.json")
    parser.add_argument("--output", type=str, default="output/output_8/results_lc_lite.json")
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--rounds", type=int, default=3, help="辩论轮次")

    args = parser.parse_args()

    # if args.claim:
    #     process_single_claim(args.claim, args.rounds)
    # elif args.dataset:
    process_dataset(args.dataset, args.output, args.max_samples)
    # else:
    #     # 默认测试
    #     test_claim = "欧盟计划在2030年全面禁止销售燃油车。"
    #     process_single_claim(test_claim, rounds=2)