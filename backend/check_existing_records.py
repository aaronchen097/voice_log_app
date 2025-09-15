#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看现有记录中的人员字段格式
用于了解正确的用户ID格式
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import get_feishu_client

def check_existing_records():
    """查看现有记录"""
    try:
        # 获取飞书客户端
        client = get_feishu_client()
        
        # 获取配置
        log_app_token = os.getenv("FEISHU_LOG_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        log_table_id = os.getenv("FEISHU_LOG_TABLE_ID", "tblReUblDhT9p1BB")
        
        print("正在查询现有记录...")
        print(f"App Token: {log_app_token}")
        print(f"Table ID: {log_table_id}")
        print("-" * 50)
        
        # 搜索记录
        records = client.search_records(
            app_token=log_app_token,
            table_id=log_table_id,
            page_size=10  # 只查看前10条记录
        )
        
        if not records:
            print("没有找到任何记录")
            return
        
        print(f"找到 {len(records)} 条记录:")
        print("-" * 50)
        
        for i, record in enumerate(records, 1):
            print(f"记录 {i}:")
            for field_name, field_value in record.items():
                if field_name == "人员":
                    print(f"  {field_name}: {field_value} (类型: {type(field_value)})")
                    # 如果是列表或字典，显示详细结构
                    if isinstance(field_value, (list, dict)):
                        import json
                        print(f"    详细结构: {json.dumps(field_value, ensure_ascii=False, indent=4)}")
                else:
                    # 截断长文本
                    if isinstance(field_value, str) and len(field_value) > 50:
                        display_value = field_value[:50] + "..."
                    else:
                        display_value = field_value
                    print(f"  {field_name}: {display_value}")
            print()
        
        # 如果有记录，提取第一个记录的人员字段作为参考
        if records and "人员" in records[0]:
            sample_user_field = records[0]["人员"]
            print("参考的人员字段格式:")
            print(f"值: {sample_user_field}")
            print(f"类型: {type(sample_user_field)}")
            if isinstance(sample_user_field, (list, dict)):
                import json
                print(f"JSON格式: {json.dumps(sample_user_field, ensure_ascii=False, indent=2)}")
        
    except Exception as e:
        print(f"查询过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_existing_records()