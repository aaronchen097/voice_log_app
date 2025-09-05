#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取飞书tenant_access_token的脚本
使用方法：python get_token.py <app_id> <app_secret>
"""

import sys
import requests
import json

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """
    获取飞书tenant_access_token
    
    Args:
        app_id: 飞书应用的App ID
        app_secret: 飞书应用的App Secret
        
    Returns:
        tenant_access_token字符串，失败返回None
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == 0:
            token = data.get("tenant_access_token")
            expire = data.get("expire")
            print(f"✅ 成功获取tenant_access_token")
            print(f"Token: {token}")
            print(f"有效期: {expire}秒 ({expire//3600}小时{(expire%3600)//60}分钟)")
            return token
        else:
            print(f"❌ 获取token失败: {data.get('msg')} (错误码: {data.get('code')})")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return None
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return None

def main():
    if len(sys.argv) != 3:
        print("使用方法: python get_token.py <app_id> <app_secret>")
        print("")
        print("示例: python get_token.py cli_xxxxxxxxx your_app_secret")
        print("")
        print("请在飞书开发者后台获取App ID和App Secret:")
        print("1. 登录 https://open.feishu.cn/")
        print("2. 选择你的应用")
        print("3. 在'基础信息 > 凭证与基础信息'页面获取App ID和App Secret")
        sys.exit(1)
    
    app_id = sys.argv[1]
    app_secret = sys.argv[2]
    
    print(f"正在获取tenant_access_token...")
    print(f"App ID: {app_id}")
    print(f"App Secret: {app_secret[:8]}...")
    print("")
    
    token = get_tenant_access_token(app_id, app_secret)
    
    if token:
        print("")
        print("请将以下token复制到.env文件中的FEISHU_ACCESS_TOKEN:")
        print(f"FEISHU_ACCESS_TOKEN={token}")
    else:
        print("")
        print("获取token失败，请检查App ID和App Secret是否正确")

if __name__ == "__main__":
    main()