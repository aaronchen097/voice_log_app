#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试飞书多维表格字段的脚本
用于查看表格中的实际字段名称，排查FieldNameNotFound错误
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import get_feishu_client
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

def debug_table_fields():
    """调试表格字段"""
    try:
        # 获取飞书客户端
        client = get_feishu_client()
        
        # 获取配置
        log_app_token = os.getenv("FEISHU_LOG_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        log_table_id = os.getenv("FEISHU_LOG_TABLE_ID", "tblReUblDhT9p1BB")
        
        print(f"正在查询表格字段...")
        print(f"App Token: {log_app_token}")
        print(f"Table ID: {log_table_id}")
        print("-" * 50)
        
        # 构造请求
        request = ListAppTableFieldRequest.builder() \
            .app_token(log_app_token) \
            .table_id(log_table_id) \
            .build()
        
        # 设置访问令牌
        option = client._build_request_option()
        
        # 发起请求
        response = client.client.bitable.v1.app_table_field.list(request, option)
        
        if not response.success():
            print(f"获取字段列表失败: {response.code} - {response.msg}")
            print(f"Log ID: {response.get_log_id()}")
            return
        
        print("表格字段列表:")
        print("-" * 50)
        
        for i, field in enumerate(response.data.items, 1):
            print(f"{i}. 字段名: '{field.field_name}'")
            print(f"   字段ID: {field.field_id}")
            print(f"   字段类型: {field.type}")
            print(f"   描述: {field.description or '无'}")
            print()
        
        # 检查我们要使用的字段是否存在
        field_names = [field.field_name for field in response.data.items]
        required_fields = ["日志内容", "人员", "语音转录结果", "AI摘要", "个人能力评估"]
        
        print("字段检查结果:")
        print("-" * 50)
        for field in required_fields:
            if field in field_names:
                print(f"✅ '{field}' - 存在")
            else:
                print(f"❌ '{field}' - 不存在")
        
        print("\n建议的字段映射:")
        print("-" * 50)
        for field in field_names:
            if "日志" in field or "内容" in field:
                print(f"'{field}' -> 可能对应 '日志内容'")
            elif "人员" in field or "用户" in field:
                print(f"'{field}' -> 可能对应 '人员'")
            elif "转录" in field or "语音" in field:
                print(f"'{field}' -> 可能对应 '语音转录结果'")
            elif "摘要" in field or "AI" in field:
                print(f"'{field}' -> 可能对应 'AI摘要'")
            elif "能力" in field or "评估" in field:
                print(f"'{field}' -> 可能对应 '个人能力评估'")
        
    except Exception as e:
        print(f"调试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_table_fields()