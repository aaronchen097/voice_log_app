#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试语音日志保存功能
用于验证修复后的代码是否能正常保存到飞书多维表格
"""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import get_feishu_client

def test_save_voice_log():
    """测试保存语音日志"""
    try:
        # 获取飞书客户端
        client = get_feishu_client()
        
        # 测试数据
        test_content = f"测试语音日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        test_user_id = "ou_7d8a6e6df7e6a0e4ed317732b2fb3c3d"  # 测试用户ID
        test_transcription = "这是一条测试的语音转录结果"
        test_summary = "这是AI生成的摘要内容"  # 这个字段不会被保存，因为表格中没有对应字段
        test_capability = "测试个人能力评估：沟通能力良好，技术理解能力强"
        
        print("开始测试语音日志保存功能...")
        print(f"测试内容: {test_content}")
        print(f"用户ID: {test_user_id}")
        print(f"转录结果: {test_transcription}")
        print(f"能力评估: {test_capability}")
        print("-" * 50)
        
        # 调用保存函数
        result = client.save_voice_log(
            content=test_content,
            user_id=test_user_id,
            transcription=test_transcription,
            summary=test_summary,  # 这个参数会被忽略
            capability_assessment=test_capability
        )
        
        if result:
            print("✅ 测试成功！语音日志已成功保存到飞书多维表格")
            print("保存的字段包括:")
            print("  - 日志内容")
            print("  - 人员")
            print("  - 语音转录结果")
            print("  - 个人能力评估")
            print("注意: AI摘要字段未保存（表格中不存在该字段）")
        else:
            print("❌ 测试失败！语音日志保存失败")
            
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_save_voice_log()