#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试更新后的 feishu_api.py 中的人员字段处理
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import FeishuBitableClient

def test_updated_api():
    """测试更新后的API处理人员字段"""
    try:
        # 获取飞书客户端
        client = FeishuBitableClient()
        
        # 测试用户ID（字符串格式）
        test_user_id = "ou_60605cb44ad9a136c662dd0b292011f5"  # 王浩维的ID
        
        print(f"测试用户ID: {test_user_id}")
        print("-" * 50)
        
        # 测试数据 - 使用字符串格式的用户ID，让API自动转换
        test_data = {
            "日志内容": "测试更新后的API - 字符串用户ID自动转换",
            "人员": test_user_id,  # 直接使用字符串，让API转换为正确格式
            "语音转录结果": "这是测试的语音转录结果",
            "个人能力评估": "技术能力：优秀\n沟通能力：良好\n学习能力：很强"
        }
        
        print("测试数据:")
        for key, value in test_data.items():
            print(f"  {key}: {value}")
        print()
        
        # 获取表格ID和应用token
        table_id = os.getenv('FEISHU_LOG_TABLE_ID')
        app_token = os.getenv('FEISHU_LOG_APP_TOKEN')
        
        if not table_id:
            print("❌ 未找到FEISHU_LOG_TABLE_ID环境变量")
            return
            
        if not app_token:
            print("❌ 未找到FEISHU_LOG_APP_TOKEN环境变量")
            return
            
        print(f"表格ID: {table_id}")
        print(f"应用Token: {app_token[:20]}...")
        
        # 尝试创建记录
        print("正在创建记录...")
        result = client.create_records(app_token, table_id, [test_data])
        
        if result:
            print("✅ 成功创建记录！")
            print(f"创建了 {len(result)} 条记录")
        else:
            print("❌ 创建记录失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_updated_api()