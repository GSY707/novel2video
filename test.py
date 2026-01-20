from modules.AI_api import llm
def test_with_messages_list():
    """测试传入消息列表的调用方式"""
    
    print("=== 测试传入消息列表 ===")
    
    # 测试用例1: 简单的单轮对话
    print("\n测试1: 单轮对话")
    messages1 = [
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
    
    try:
        # 注意：原始代码中 llm 函数期望的是字符串，所以这里需要修改函数签名
        # 但按照你的要求，我们演示如何调用
        response = llm(messages1, "Qwen")
        print(f"Qwen 回复: {response[:200]}...")
    except Exception as e:
        print(f"测试1失败: {e}")
    
    # 测试用例2: 多轮对话
    print("\n测试2: 多轮对话")
    messages2 = [
        {"role": "user", "content": "请帮我写一首关于春天的诗"},
        {"role": "assistant", "content": "好的，这是一首关于春天的诗：\n春风拂面花开放，\n万物复苏生机盎。"},
        {"role": "user", "content": "很好，请继续完成这首诗"}
    ]
    
    try:
        response = llm(messages2, "DeepSeek")
        print(f"DeepSeek 回复: {response[:200]}...")
    except Exception as e:
        print(f"测试2失败: {e}")
    
    # 测试用例3: 系统指令 + 用户对话
    print("\n测试3: 系统指令 + 用户对话")
    messages3 = [
        {"role": "system", "content": "你是一个专业的中文诗歌创作助手，擅长创作五言和七言绝句。"},
        {"role": "user", "content": "请写一首关于月亮的五言绝句"}
    ]
    
    try:
        response = llm(messages3, "Qwen")
        print(f"Qwen 回复: {response[:200]}...")
    except Exception as e:
        print(f"测试3失败: {e}")

test_with_messages_list()