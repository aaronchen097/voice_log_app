#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书Token自动管理器
用于自动获取和刷新tenant_access_token
"""

import os
import time
import threading
import requests
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FeishuTokenManager:
    """
    飞书Token自动管理器
    
    功能：
    1. 自动获取tenant_access_token
    2. 定时刷新token（在过期前自动刷新）
    3. 线程安全的token访问
    4. 错误重试机制
    """
    
    def __init__(self, app_id: str, app_secret: str, refresh_margin: int = 300):
        """
        初始化Token管理器
        
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            refresh_margin: 提前刷新时间（秒），默认300秒（5分钟）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.refresh_margin = refresh_margin
        
        self._token = None
        self._expire_time = None
        self._lock = threading.Lock()
        self._refresh_timer = None
        
        # API配置
        self.api_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        self.headers = {"Content-Type": "application/json; charset=utf-8"}
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1  # 秒
        
    def _fetch_token(self) -> Optional[Dict]:
        """
        从飞书API获取token
        
        Returns:
            包含token和过期时间的字典，失败返回None
        """
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url, 
                    json=payload, 
                    headers=self.headers,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("code") == 0:
                    token = data.get("tenant_access_token")
                    expire = data.get("expire", 7200)  # 默认2小时
                    
                    logger.info(f"成功获取token，有效期: {expire}秒")
                    return {
                        "token": token,
                        "expire_time": datetime.now() + timedelta(seconds=expire)
                    }
                else:
                    logger.error(f"获取token失败: {data.get('msg')} (错误码: {data.get('code')})")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"获取token请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # 递增延迟
            except Exception as e:
                logger.error(f"获取token时发生未知错误: {e}")
                return None
        
        logger.error("获取token失败，已达到最大重试次数")
        return None
    
    def _schedule_refresh(self):
        """
        安排下次token刷新
        """
        if self._expire_time is None:
            return
            
        # 计算刷新时间（过期前refresh_margin秒）
        refresh_time = self._expire_time - timedelta(seconds=self.refresh_margin)
        delay = (refresh_time - datetime.now()).total_seconds()
        
        if delay > 0:
            logger.info(f"安排在 {refresh_time.strftime('%Y-%m-%d %H:%M:%S')} 刷新token")
            self._refresh_timer = threading.Timer(delay, self._refresh_token)
            self._refresh_timer.daemon = True
            self._refresh_timer.start()
        else:
            # 如果已经过期或即将过期，立即刷新
            logger.warning("Token即将过期或已过期，立即刷新")
            self._refresh_token()
    
    def _refresh_token(self):
        """
        刷新token（内部方法）
        """
        logger.info("开始刷新token...")
        
        with self._lock:
            token_data = self._fetch_token()
            if token_data:
                self._token = token_data["token"]
                self._expire_time = token_data["expire_time"]
                logger.info(f"Token刷新成功，新token: {self._token[:20]}...")
                
                # 安排下次刷新
                self._schedule_refresh()
            else:
                logger.error("Token刷新失败")
                # 如果刷新失败，5分钟后重试
                self._refresh_timer = threading.Timer(300, self._refresh_token)
                self._refresh_timer.daemon = True
                self._refresh_timer.start()
    
    def get_token(self) -> Optional[str]:
        """
        获取有效的token
        
        Returns:
            有效的token字符串，失败返回None
        """
        with self._lock:
            # 检查是否需要获取新token
            if (self._token is None or 
                self._expire_time is None or 
                datetime.now() >= self._expire_time - timedelta(seconds=self.refresh_margin)):
                
                logger.info("需要获取新token")
                token_data = self._fetch_token()
                if token_data:
                    self._token = token_data["token"]
                    self._expire_time = token_data["expire_time"]
                    
                    # 安排自动刷新
                    self._schedule_refresh()
                else:
                    return None
            
            return self._token
    
    def is_token_valid(self) -> bool:
        """
        检查当前token是否有效
        
        Returns:
            True如果token有效，False否则
        """
        with self._lock:
            return (self._token is not None and 
                    self._expire_time is not None and 
                    datetime.now() < self._expire_time)
    
    def get_token_info(self) -> Dict:
        """
        获取token信息
        
        Returns:
            包含token状态信息的字典
        """
        with self._lock:
            if self._token and self._expire_time:
                remaining = (self._expire_time - datetime.now()).total_seconds()
                return {
                    "token": self._token,
                    "expire_time": self._expire_time.isoformat(),
                    "remaining_seconds": max(0, int(remaining)),
                    "is_valid": remaining > 0
                }
            else:
                return {
                    "token": None,
                    "expire_time": None,
                    "remaining_seconds": 0,
                    "is_valid": False
                }
    
    def stop(self):
        """
        停止token管理器
        """
        if self._refresh_timer:
            self._refresh_timer.cancel()
            logger.info("Token管理器已停止")


# 全局token管理器实例
_token_manager = None

def get_token_manager() -> Optional[FeishuTokenManager]:
    """
    获取全局token管理器实例
    
    Returns:
        FeishuTokenManager实例，如果未初始化返回None
    """
    return _token_manager

def init_token_manager(app_id: str = None, app_secret: str = None) -> FeishuTokenManager:
    """
    初始化全局token管理器
    
    Args:
        app_id: 飞书应用ID，如果为None则从环境变量获取
        app_secret: 飞书应用密钥，如果为None则从环境变量获取
        
    Returns:
        FeishuTokenManager实例
    """
    global _token_manager
    
    if app_id is None:
        app_id = os.getenv('FEISHU_APP_ID')
    if app_secret is None:
        app_secret = os.getenv('FEISHU_APP_SECRET')
    
    if not app_id or not app_secret:
        raise ValueError("App ID和App Secret不能为空")
    
    _token_manager = FeishuTokenManager(app_id, app_secret)
    logger.info("Token管理器初始化完成")
    return _token_manager

def get_current_token() -> Optional[str]:
    """
    获取当前有效token
    
    Returns:
        有效的token字符串，失败返回None
    """
    if _token_manager:
        return _token_manager.get_token()
    else:
        logger.warning("Token管理器未初始化")
        return None