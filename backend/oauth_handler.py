import os
import json
import time
import logging
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeishuOAuthHandler:
    """飞书OAuth认证处理器"""
    
    def __init__(self):
        self.app_id = os.getenv('FEISHU_APP_ID')
        self.app_secret = os.getenv('FEISHU_APP_SECRET')
        self.redirect_uri = os.getenv('FEISHU_REDIRECT_URI')
        
        if not all([self.app_id, self.app_secret, self.redirect_uri]):
            logger.error("飞书OAuth配置不完整，请检查环境变量")
            raise ValueError("Missing Feishu OAuth configuration")
        
        # 内存存储token信息（生产环境建议使用数据库）
        self.token_storage = {}
        # 存储tenant_access_token
        self.tenant_token_storage = {}
    
    def get_authorization_url(self, state: str = "default") -> str:
        """获取飞书授权URL"""
        params = {
            'client_id': self.app_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'bitable:app:readonly contact:user.base:readonly',
            'state': state,
            'response_type': 'code'
        }
        
        base_url = 'https://accounts.feishu.cn/open-apis/authen/v1/authorize'
        return f"{base_url}?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """用授权码换取access_token"""
        url = 'https://open.feishu.cn/open-apis/authen/v2/oauth/token'
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            result = response.json()
            
            if result.get('code') == 0:
                token_info = {
                    'access_token': result['access_token'],
                    'refresh_token': result.get('refresh_token'),
                    'expires_in': result['expires_in'],
                    'expires_at': time.time() + result['expires_in'],
                    'scope': result.get('scope', '')
                }
                
                # 存储token信息
                self.token_storage['current'] = token_info
                logger.info("成功获取user_access_token")
                return token_info
            else:
                logger.error(f"获取token失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"交换token时发生错误: {e}")
            return None
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """刷新access_token"""
        url = 'https://open.feishu.cn/open-apis/authen/v2/oauth/token'
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'refresh_token': refresh_token
        }
        
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            result = response.json()
            
            if result.get('code') == 0:
                token_info = {
                    'access_token': result['access_token'],
                    'refresh_token': result.get('refresh_token'),
                    'expires_in': result['expires_in'],
                    'expires_at': time.time() + result['expires_in'],
                    'scope': result.get('scope', '')
                }
                
                # 更新token信息
                self.token_storage['current'] = token_info
                logger.info("成功刷新user_access_token")
                return token_info
            else:
                logger.error(f"刷新token失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"刷新token时发生错误: {e}")
            return None
    
    def get_valid_token(self) -> Optional[str]:
        """获取有效的access_token，如果过期则自动刷新"""
        current_token = self.token_storage.get('current')
        
        if not current_token:
            logger.warning("没有可用的token，需要重新授权")
            return None
        
        # 检查token是否即将过期（提前5分钟刷新）
        if current_token['expires_at'] - time.time() < 300:
            logger.info("Token即将过期，尝试刷新")
            
            if current_token.get('refresh_token'):
                refreshed = self.refresh_token(current_token['refresh_token'])
                if refreshed:
                    return refreshed['access_token']
            
            logger.warning("Token刷新失败，需要重新授权")
            return None
        
        return current_token['access_token']
    
    def validate_token_with_api(self, token: str) -> bool:
        """通过API验证token是否有效"""
        url = 'https://open.feishu.cn/open-apis/authen/v1/user_info'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                logger.info("Token验证成功")
                return True
            elif result.get('code') == 99991663:  # token无效
                logger.warning("Token已失效")
                return False
            else:
                logger.error(f"Token验证失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Token验证时发生错误: {e}")
            return False
    
    def handle_api_error(self, error_response: Dict[str, Any]) -> str:
        """处理飞书API错误响应"""
        error_code = error_response.get('code')
        error_msg = error_response.get('msg', '未知错误')
        
        error_messages = {
            99991663: "user_access_token无效，需要重新授权",
            99991664: "user_access_token已过期，尝试刷新token",
            99991665: "应用未获得相应权限，请检查应用权限配置",
            99991666: "用户未安装应用，请先安装应用",
            99991667: "用户未授权应用相应权限，请重新授权"
        }
        
        if error_code in error_messages:
            return error_messages[error_code]
        else:
            return f"API调用失败: {error_msg} (错误代码: {error_code})"
    
    def is_token_valid(self) -> bool:
        """检查当前token是否有效"""
        return self.get_valid_token() is not None
    
    def clear_token(self):
        """清除存储的token信息"""
        self.token_storage.clear()
        self.tenant_token_storage.clear()
        logger.info("已清除所有token信息")
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """获取当前token信息"""
        return self.token_storage.get('current')
    
    def get_tenant_access_token(self) -> Optional[str]:
        """获取tenant_access_token，用于应用级别的API调用"""
        # 检查是否有有效的tenant_access_token
        current_tenant_token = self.tenant_token_storage.get('current')
        
        if current_tenant_token:
            # 检查token是否即将过期（提前5分钟刷新）
            if current_tenant_token['expires_at'] - time.time() > 300:
                return current_tenant_token['access_token']
        
        # 获取新的tenant_access_token
        return self._fetch_tenant_access_token()
    
    def _fetch_tenant_access_token(self) -> Optional[str]:
        """从飞书API获取tenant_access_token"""
        url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
        
        data = {
            'app_id': self.app_id,
            'app_secret': self.app_secret
        }
        
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            result = response.json()
            
            if result.get('code') == 0:
                token_info = {
                    'access_token': result['tenant_access_token'],
                    'expires_in': result['expire'],
                    'expires_at': time.time() + result['expire']
                }
                
                # 存储token信息
                self.tenant_token_storage['current'] = token_info
                logger.info("成功获取tenant_access_token")
                return token_info['access_token']
            else:
                logger.error(f"获取tenant_access_token失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"获取tenant_access_token时发生错误: {e}")
            return None
    
    def get_access_token_for_api(self, prefer_tenant: bool = False) -> Optional[str]:
        """根据需要获取合适的access_token
        
        Args:
            prefer_tenant: 是否优先使用tenant_access_token
        
        Returns:
            适合的access_token
        """
        if prefer_tenant:
            # 优先使用tenant_access_token
            tenant_token = self.get_tenant_access_token()
            if tenant_token:
                return tenant_token
            # 如果tenant_access_token不可用，回退到user_access_token
            return self.get_valid_token()
        else:
            # 优先使用user_access_token
            user_token = self.get_valid_token()
            if user_token:
                return user_token
            # 如果user_access_token不可用，回退到tenant_access_token
            return self.get_tenant_access_token()

# 全局OAuth处理器实例（延迟初始化）
oauth_handler = None

def get_oauth_handler():
    """获取OAuth处理器实例，支持延迟初始化"""
    global oauth_handler
    if oauth_handler is None:
        oauth_handler = FeishuOAuthHandler()
    return oauth_handler