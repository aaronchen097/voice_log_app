#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试不同的人员字段格式
用于找出正确的人员字段格式，解决UserFieldConvFail错误
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

def test_different_user_formats():
    """测试不同的用户字段格式"""
    try:
        # 获取飞书客户端
        client = get_feishu_client()
        
        # 获取配置
        log_app_token = os.getenv("FEISHU_LOG_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        log_table_id = os.getenv("FEISHU_LOG_TABLE_ID", "tblReUblDhT9p1BB")
        
        # 测试不同的用户ID格式
        test_formats = [
            {
                "name": "格式1: 直接使用用户ID字符串",
                "user_data": "ou_7d8a6e6df7e6a0e4ed317732b2fb3c3d"
            },
            {
                "name": "格式2: 使用对象数组格式 [{\"id\": \"user_id\"}]",
                "user_data": [{"id": "ou_7d8a6e6df7e6a0e4ed317732b2fb3c3d"}]
            },
            {
                "name": "格式3: 使用简单数组格式 [\"user_id\"]",
                "user_data": ["ou_7d8a6e6df7e6a0e4ed317732b2fb3c3d"]
            },
            {
                "name": "格式4: 使用对象格式 {\"id\": \"user_id\"}",
                "user_data": {"id": "ou_7d8a6e6df7e6a0e4ed317732b2fb3c3d"}
            }
        ]
        
        for i, test_format in enumerate(test_formats, 1):
            print(f"\n测试 {i}: {test_format['name']}")
            print(f"用户数据格式: {test_format['user_data']}")
            print("-" * 60)
            
            try:
                # 准备测试数据
                test_data = {
                    "日志内容": f"测试人员字段格式 {i} - {datetime.now().strftime('%H:%M:%S')}",
                    "人员": test_format['user_data'],
                    "语音转录结果": f"测试转录结果 {i}",
                    "个人能力评估": f"测试能力评估 {i}"
                }
                
                # 尝试创建记录
                result = client.create_records(
                    app_token=log_app_token,
                    table_id=log_table_id,
                    records_to_create=[test_data]
                )
                
                if result:
                    print(f"✅ 格式 {i} 成功！记录ID: {result[0].record_id}")
                    print("这是正确的人员字段格式")
                    break
                else:
                    print(f"❌ 格式 {i} 失败")
                    
            except Exception as e:
                print(f"❌ 格式 {i} 出错: {str(e)}")
        
        print("\n测试完成")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_different_user_formats()