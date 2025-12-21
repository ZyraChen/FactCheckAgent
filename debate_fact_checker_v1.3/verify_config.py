"""
验证性能优化配置 - 静态检查
"""

import re
from pathlib import Path


def check_file_content(filepath, patterns, desc):
    """检查文件内容是否包含指定模式"""
    print(f"\n检查 {desc}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    all_found = True
    for pattern, expected in patterns:
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"  ✓ 找到: {expected}")
        else:
            print(f"  ✗ 缺失: {expected}")
            all_found = False

    return all_found


def main():
    print("=" * 80)
    print("性能优化配置验证")
    print("=" * 80)

    base_dir = Path(__file__).parent
    all_passed = True

    # 1. 检查 QwenClient.chat() 是否添加了搜索参数
    patterns = [
        (r'enable_search:\s*bool\s*=\s*False', '添加 enable_search 参数'),
        (r'force_search:\s*bool\s*=\s*False', '添加 force_search 参数'),
        (r'search_strategy:\s*str\s*=\s*["\']auto["\']', '添加 search_strategy 参数'),
        (r'if enable_search:', '根据参数构建 extra_body'),
    ]
    result = check_file_content(
        base_dir / 'llm/qwen_client.py',
        patterns,
        'QwenClient.chat() 搜索参数'
    )
    all_passed = all_passed and result

    # 2. 检查 QwenLLMWrapper 是否添加了属性
    patterns = [
        (r'enable_search:\s*bool\s*=\s*False', '添加 enable_search 属性'),
        (r'force_search:\s*bool\s*=\s*False', '添加 force_search 属性'),
        (r'search_strategy:\s*str\s*=\s*["\']auto["\']', '添加 search_strategy 属性'),
        (r'kwargs\.get\(["\']enable_search["\'],\s*self\.enable_search\)', '传递 enable_search 给 QwenClient'),
    ]
    result = check_file_content(
        base_dir / 'utils/qwen_wrapper.py',
        patterns,
        'QwenLLMWrapper 配置属性'
    )
    all_passed = all_passed and result

    # 3. 检查 workflow 是否为每个 Chain 创建了独立的 LLM
    patterns = [
        (r'pro_llm\s*=\s*QwenLLMWrapper.*enable_search=True.*force_search=False', 'Pro LLM 配置'),
        (r'con_llm\s*=\s*QwenLLMWrapper.*enable_search=True.*force_search=False', 'Con LLM 配置'),
        (r'judge_llm\s*=\s*QwenLLMWrapper.*enable_search=False', 'Judge LLM 配置'),
        (r'ProQueryChain\(llm=pro_llm\)', '使用 pro_llm 创建 ProQueryChain'),
        (r'ConQueryChain\(llm=con_llm\)', '使用 con_llm 创建 ConQueryChain'),
        (r'JudgeChain\(llm=judge_llm\)', '使用 judge_llm 创建 JudgeChain'),
    ]
    result = check_file_content(
        base_dir / 'workflow/debate_workflow_lc.py',
        patterns,
        'Workflow 中的 LLM 配置'
    )
    all_passed = all_passed and result

    # 4. 检查 AttackDetector 是否关闭搜索
    patterns = [
        (r'enable_search=False', 'AttackDetector 关闭搜索'),
    ]
    result = check_file_content(
        base_dir / 'tools/attack_detector.py',
        patterns,
        'AttackDetector 搜索配置'
    )
    all_passed = all_passed and result

    # 5. 检查 JudgeChain.determine_stance 是否临时关闭搜索
    patterns = [
        (r'self\.llm\.enable_search\s*=\s*False.*determine_stance', '临时关闭搜索'),
        (r'finally:.*self\.llm\.enable_search\s*=\s*original_search', '恢复原始配置'),
    ]
    result = check_file_content(
        base_dir / 'chains/judge_chain.py',
        patterns,
        'JudgeChain.determine_stance 配置'
    )
    all_passed = all_passed and result

    # 6. 检查 JudgeChain.make_verdict 是否启用完整搜索
    patterns = [
        (r'self\.llm\.enable_search\s*=\s*True', '启用搜索'),
        (r'self\.llm\.force_search\s*=\s*True', '强制搜索'),
        (r'self\.llm\.search_strategy\s*=\s*["\']max["\']', '最大搜索策略'),
    ]
    result = check_file_content(
        base_dir / 'chains/judge_chain.py',
        patterns,
        'JudgeChain.make_verdict 配置'
    )
    all_passed = all_passed and result

    print("\n" + "=" * 80)
    if all_passed:
        print("✓ 所有配置检查通过！")
        print("\n配置摘要:")
        print("-" * 80)
        print("环节                 | enable_search | force_search | 说明")
        print("-" * 80)
        print("Pro 查询生成         | True          | False        | 智能搜索")
        print("Con 查询生成         | True          | False        | 智能搜索")
        print("攻击检测             | False         | False        | 关闭搜索")
        print("立场判断             | False         | False        | 关闭搜索")
        print("最终判决             | True          | True         | 强制搜索(max)")
        print("-" * 80)
        print("\n预期性能提升: 从 17分钟 降至 3分钟 (提速约 6倍)")
    else:
        print("✗ 部分配置检查失败，请检查上述错误")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
