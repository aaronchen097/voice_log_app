#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 save_voice_log 方法
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import FeishuBitableClient

def test_save_voice_log():
    """测试保存语音日志功能"""
    try:
        # 获取飞书客户端
        client = FeishuBitableClient()
        
        # 测试用户ID
        test_user_id = "ou_60605cb44ad9a136c662dd0b292011f5"  # 王浩维的ID
        
        print(f"测试用户ID: {test_user_id}")
        print("-" * 50)
        
        # 测试保存语音日志
        content = "这是一条测试语音日志，用于验证save_voice_log方法是否正常工作。"
        transcription = "这是语音转录的结果文本。"
        summary = "这是AI生成的摘要内容。"  # 注意：表格中没有AI摘要字段
        capability_assessment = "技术能力：优秀\n沟通能力：良好\n学习能力：很强\n解决问题能力：出色"
        
        print("测试数据:")
        print(f"  内容: {content}")
        print(f"  用户ID: {test_user_id}")
        print(f"  转录结果: {transcription}")
        print(f"  摘要: {summary}")
        print(f"  能力评估: {capability_assessment}")
        print()
        
        # 调用save_voice_log方法
        print("正在保存语音日志...")
        result = client.save_voice_log(
            content=content,
            user_id=test_user_id,
            transcription=transcription,
            summary=summary,
            capability_assessment=capability_assessment
        )
        
        if result:
            print("✅ 成功保存语音日志！")
        else:
            print("❌ 保存语音日志失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_save_voice_log()