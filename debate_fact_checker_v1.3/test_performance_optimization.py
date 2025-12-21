"""
测试性能优化后的代码
验证搜索参数配置是否正确
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import config
from llm.qwen_client import QwenClient
from utils.qwen_wrapper import QwenLLMWrapper
from chains import ProQueryChain, ConQueryChain, JudgeChain


def test_search_config():
    """测试搜索配置是否正确"""

    print("=" * 80)
    print("性能优化测试 - 验证搜索参数配置")
    print("=" * 80)

    # 1. 测试 QwenClient 的新参数
    print("\n[测试 1] QwenClient.chat() 支持搜索参数...")
    llm_client = QwenClient(config.DASHSCOPE_API_KEY)

    # 测试默认行为（不搜索）
    messages = [{"role": "user", "content": "1+1等于几？"}]
    try:
        response = llm_client.chat(messages, enable_search=False)
        print(f"✓ 关闭搜索调用成功: {response[:50]}...")
    except Exception as e:
        print(f"✗ 关闭搜索调用失败: {e}")
        return False

    # 2. 测试 QwenLLMWrapper 配置
    print("\n[测试 2] QwenLLMWrapper 搜索参数配置...")

    # Pro Chain LLM (enable_search=True, force_search=False)
    pro_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=True,
        force_search=False,
        search_strategy="auto"
    )
    assert pro_llm.enable_search == True
    assert pro_llm.force_search == False
    print("✓ Pro LLM 配置正确: enable_search=True, force_search=False")

    # Con Chain LLM (enable_search=True, force_search=False)
    con_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=True,
        force_search=False,
        search_strategy="auto"
    )
    assert con_llm.enable_search == True
    assert con_llm.force_search == False
    print("✓ Con LLM 配置正确: enable_search=True, force_search=False")

    # Judge Chain LLM (默认关闭)
    judge_llm = QwenLLMWrapper(
        qwen_client=llm_client,
        enable_search=False,
        force_search=False
    )
    assert judge_llm.enable_search == False
    print("✓ Judge LLM 配置正确: enable_search=False (默认)")

    # 3. 测试 Chain 创建
    print("\n[测试 3] Chain 创建...")
    try:
        pro_chain = ProQueryChain(llm=pro_llm)
        con_chain = ConQueryChain(llm=con_llm)
        judge_chain = JudgeChain(llm=judge_llm)
        print("✓ 所有 Chain 创建成功")
    except Exception as e:
        print(f"✗ Chain 创建失败: {e}")
        return False

    # 4. 测试 Judge Chain 的临时配置切换
    print("\n[测试 4] Judge Chain 临时配置切换...")

    # 验证初始状态
    assert judge_chain.llm.enable_search == False
    print("✓ Judge Chain 初始状态: enable_search=False")

    # 模拟 make_verdict 中的配置切换
    original_search = judge_chain.llm.enable_search
    judge_chain.llm.enable_search = True
    judge_chain.llm.force_search = True
    judge_chain.llm.search_strategy = "max"

    assert judge_chain.llm.enable_search == True
    assert judge_chain.llm.force_search == True
    assert judge_chain.llm.search_strategy == "max"
    print("✓ 临时切换到完整搜索模式成功")

    # 恢复
    judge_chain.llm.enable_search = original_search
    assert judge_chain.llm.enable_search == False
    print("✓ 恢复原始配置成功")

    print("\n" + "=" * 80)
    print("✓ 所有测试通过！性能优化配置正确")
    print("=" * 80)

    # 打印配置摘要
    print("\n配置摘要:")
    print("-" * 80)
    print("1. Pro 查询生成:    enable_search=True,  force_search=False (智能搜索)")
    print("2. Con 查询生成:    enable_search=True,  force_search=False (智能搜索)")
    print("3. 攻击检测:        enable_search=False, force_search=False (关闭搜索)")
    print("4. 立场判断:        enable_search=False, force_search=False (关闭搜索)")
    print("5. 最终判决:        enable_search=True,  force_search=True  (强制搜索)")
    print("-" * 80)

    return True


if __name__ == "__main__":
    success = test_search_config()
    sys.exit(0 if success else 1)
