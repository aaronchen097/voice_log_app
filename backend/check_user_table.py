#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看用户表中的用户信息
用于获取有效的用户ID
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import get_feishu_client

def check_user_table():
    """查看用户表"""
    try:
        # 获取飞书客户端
        client = get_feishu_client()
        
        # 获取用户表配置
        user_app_token = os.getenv("FEISHU_USER_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        user_table_id = os.getenv("FEISHU_USER_TABLE_ID", "tblp6HXTjdkOjX10")
        
        print("正在查询用户表...")
        print(f"User App Token: {user_app_token}")
        print(f"User Table ID: {user_table_id}")
        print("-" * 50)
        
        # 搜索用户记录
        users = client.search_records(
            app_token=user_app_token,
            table_id=user_table_id,
            page_size=10  # 只查看前10个用户
        )
        
        if not users:
            print("用户表中没有找到任何用户")
            return
        
        print(f"找到 {len(users)} 个用户:")
        print("-" * 50)
        
        for i, user in enumerate(users, 1):
            print(f"用户 {i}:")
            print(f"  记录ID: {user.record_id}")
            
            # 访问字段数据
            if hasattr(user, 'fields') and user.fields:
                for field_name, field_value in user.fields.items():
                    # 显示所有字段
                    if isinstance(field_value, str) and len(field_value) > 100:
                        display_value = field_value[:100] + "..."
                    else:
                        display_value = field_value
                    print(f"  {field_name}: {display_value} (类型: {type(field_value)})")
                    
                    # 如果是人员字段，显示详细结构
                    if "人员" in field_name or "用户" in field_name:
                        if isinstance(field_value, (list, dict)):
                            import json
                            print(f"    详细结构: {json.dumps(field_value, ensure_ascii=False, indent=4)}")
            else:
                print("  无字段数据")
            print()
        
        # 提取第一个用户的ID作为测试用例
        if users:
            first_user = users[0]
            print("可用于测试的用户信息:")
            print("-" * 30)
            print(f"记录ID: {first_user.record_id}")
            
            # 查找可能的用户ID字段
            possible_id_fields = []
            if hasattr(first_user, 'fields') and first_user.fields:
                for field_name, field_value in first_user.fields.items():
                    if any(keyword in field_name.lower() for keyword in ['id', '人员', '用户', 'user']):
                        possible_id_fields.append((field_name, field_value))
                
                if possible_id_fields:
                    print("可能的用户ID字段:")
                    for field_name, field_value in possible_id_fields:
                        print(f"  {field_name}: {field_value}")
                else:
                    print("未找到明显的用户ID字段")
            else:
                print("无字段数据可分析")
        
    except Exception as e:
        print(f"查询过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_user_table()