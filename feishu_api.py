import os
import time
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    SearchAppTableRecordRequest, 
    SearchAppTableRecordRequestBody,
    BatchCreateAppTableRecordRequest, 
    BatchCreateAppTableRecordRequestBody, 
    AppTableRecord
)
import pandas as pd
from token_manager import get_token_manager, init_token_manager, get_current_token


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class FeishuBitableClient:
    """飞书多维表格客户端"""
    
    def __init__(self, access_token: Optional[str] = None, debug: bool = False, auto_token_refresh: bool = True):
        self.access_token = access_token or os.getenv("FEISHU_ACCESS_TOKEN")
        self.auto_token_refresh = auto_token_refresh
        self.client = self._build_client(debug)
        
        # 初始化token管理器（如果启用自动刷新）
        if self.auto_token_refresh:
            try:
                app_id = os.getenv('FEISHU_APP_ID')
                app_secret = os.getenv('FEISHU_APP_SECRET')
                if app_id and app_secret:
                    # 如果有App ID和Secret，初始化token管理器
                    if not get_token_manager():
                        init_token_manager(app_id, app_secret)
                    logger.info("Token管理器已启用，将自动刷新token")
                else:
                    logger.warning("未找到FEISHU_APP_ID或FEISHU_APP_SECRET，使用静态token")
                    self.auto_token_refresh = False
            except Exception as e:
                logger.error(f"初始化token管理器失败: {e}，使用静态token")
                self.auto_token_refresh = False
        
        # 配置信息 - 从环境变量读取
        self.user_app_token = os.getenv("FEISHU_USER_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        self.user_table_id = os.getenv("FEISHU_USER_TABLE_ID", "tblp6HXTjdkOjX10")
        self.log_app_token = os.getenv("FEISHU_LOG_APP_TOKEN", "HSvLb0OOBajIF2sXWPEc7NednXd")
        self.log_table_id = os.getenv("FEISHU_LOG_TABLE_ID", "tblReUblDhT9p1BB")
        
    def _build_client(self, debug: bool = False) -> lark.Client:
        """构建飞书客户端"""
        return (
            lark.Client.builder()
            .enable_set_token(True)  # 允许在 RequestOption 里设置 user_access_token
            .log_level(lark.LogLevel.DEBUG if debug else lark.LogLevel.ERROR)
            .build()
        )
    
    def _build_request_option(self, token: Optional[str] = None, prefer_tenant: bool = False) -> lark.RequestOption:
        """根据 token 前缀 (t- or u-) 自动构建使用 tenant_access_token 或 user_access_token 的 RequestOption。"""
        # 优先使用传入的token，然后尝试从token管理器获取，最后使用实例token
        if not token and self.auto_token_refresh:
            try:
                token = get_current_token()
                if token:
                    logger.debug("使用token管理器获取的token")
            except Exception as e:
                logger.warning(f"从token管理器获取token失败: {e}，使用备用token")
        
        if not token:
            token = self.access_token
            
        option_builder = lark.RequestOption.builder()
        if not token:
            logger.warning("没有可用的访问令牌")
            return option_builder.build()
        
        if token.startswith("t-"):
            option_builder.tenant_access_token(token)
            logger.debug("使用tenant_access_token")
        else:  # 默认为 user_access_token (u- 或其他)
            option_builder.user_access_token(token)
            logger.debug("使用user_access_token")
            
        return option_builder.build()
    
    def search_records(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None,
        field_names: Optional[List[str]] = None,
        page_size: int = 500,
        max_pages: Optional[int] = None,
        sleep_on_rate_limit: float = 1.5,
        prefer_tenant: bool = False
    ) -> List[Dict[str, Any]]:
        """
        拉取多维表格所有匹配记录（分页累积）
        
        :param app_token: 应用(多维表格) token
        :param table_id: 表 ID
        :param view_id: 视图 ID (可选)
        :param field_names: 需要的字段名列表 (可选，不填返回全部字段)
        :param page_size: 每页条数（官方上限参考文档）
        :param max_pages: 限制最多页数（防止无限抓取）
        :param sleep_on_rate_limit: 429 时休眠秒数
        :return: 记录列表
        """
        all_records: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        page_count = 0

        while True:
            body_builder = SearchAppTableRecordRequestBody.builder()
            if view_id:
                body_builder.view_id(view_id)
            if field_names:
                body_builder.field_names(field_names)

            body = body_builder.build()

            req_builder = (
                SearchAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .page_size(page_size)
                .request_body(body)
            )
            if page_token:
                req_builder.page_token(page_token)

            request = req_builder.build()
            option = self._build_request_option(prefer_tenant=prefer_tenant)

            response = self.client.bitable.v1.app_table_record.search(request, option)

            # 失败处理
            if not response.success():
                # 简单的 429 重试逻辑
                if response.code == 429:
                    logger.warning("触发限频，休眠 %.1f 秒后重试...", sleep_on_rate_limit)
                    time.sleep(sleep_on_rate_limit)
                    continue
                
                # 处理token相关错误
                if response.code in [99991663, 99991664]:  # token无效或过期
                    if self.oauth_handler:
                        error_msg = self.oauth_handler.handle_api_error({
                            'code': response.code,
                            'msg': response.msg
                        })
                        logger.error(f"Token错误: {error_msg}")
                        
                        # 尝试刷新token
                        if response.code == 99991664:  # token过期
                            new_token = self.oauth_handler.get_valid_token()
                            if new_token:
                                logger.info("Token已刷新，重试请求")
                                continue
                    
                logger.error(
                    "调用失败 code=%s msg=%s log_id=%s",
                    response.code,
                    response.msg,
                    response.get_log_id()
                )
                try:
                    raw_json = json.loads(response.raw.content)
                    logger.error(json.dumps(raw_json, indent=2, ensure_ascii=False))
                except Exception:
                    pass
                break

            data = response.data
            records = data.items or []
            all_records.extend(records)

            page_count += 1
            logger.info("已获取 %d 条 (第 %d 页)", len(all_records), page_count)

            page_token = data.page_token
            if not page_token:
                break
            if max_pages and page_count >= max_pages:
                break

        return all_records
    
    def create_records(
        self,
        app_token: str,
        table_id: str,
        records_to_create: List[Dict[str, Any]]
    ) -> Optional[List[AppTableRecord]]:
        """
        向飞书多维表格批量写入数据。
        
        :param app_token: 多维表格的 app_token。
        :param table_id: 表格的 table_id。
        :param records_to_create: 待创建的记录列表。每个元素是一个字典，key为字段名，value为该字段的值。
        :return: 成功时返回新创建的记录对象列表，否则返回 None。
        """
        lark_records = []
        for record_data in records_to_create:
            fields = {}
            for field_name, value in record_data.items():
                # 根据字段类型对数据进行格式化
                if field_name == "人员" and isinstance(value, str):
                    # 人员字段需要构造成 [{ "id": "ou_xxx" }] 的形式
                    fields[field_name] = [{"id": value}]
                elif field_name in ["账号", "密码", "日志内容"] and isinstance(value, str):
                    # 文本字段可以直接使用字符串
                    fields[field_name] = value
                else:
                    fields[field_name] = value
            
            lark_records.append(AppTableRecord.builder().fields(fields).build())

        # 构造请求体
        request_body = BatchCreateAppTableRecordRequestBody.builder() \
            .records(lark_records) \
            .build()

        # 构造请求
        request = BatchCreateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(request_body) \
            .build()

        # 设置访问令牌
        option = self._build_request_option()

        # 发起请求
        response = self.client.bitable.v1.app_table_record.batch_create(request, option)

        # 处理返回结果
        if not response.success():
            logger.error(
                f"批量创建记录失败, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
            return None

        logger.info(f"成功创建 {len(response.data.records)} 条记录。")
        return response.data.records
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        用户认证
        
        :param username: 用户名
        :param password: 密码
        :return: 用户信息字典，包含用户ID等信息，认证失败返回None
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 查询用户表中的所有记录，使用tenant_access_token
                records = self.search_records(
                    app_token=self.user_app_token,
                    table_id=self.user_table_id,
                    field_names=["账号", "密码", "提交人"],
                    prefer_tenant=True
                )
                
                # 遍历记录查找匹配的用户
                for record in records:
                    fields = record.fields or {}
                    
                    # 提取账号信息
                    account_field = fields.get("账号")
                    if isinstance(account_field, list) and account_field:
                        account = account_field[0].get('text', '') if 'text' in account_field[0] else str(account_field[0])
                    else:
                        account = str(account_field) if account_field else ''
                    
                    # 提取密码信息
                    password_field = fields.get("密码")
                    if isinstance(password_field, list) and password_field:
                        stored_password = password_field[0].get('text', '') if 'text' in password_field[0] else str(password_field[0])
                    else:
                        stored_password = str(password_field) if password_field else ''
                    
                    # 提取用户ID信息
                    user_id_field = fields.get("提交人")
                    if isinstance(user_id_field, list) and user_id_field:
                        user_id = user_id_field[0].get('id', '') if 'id' in user_id_field[0] else str(user_id_field[0])
                    else:
                        user_id = str(user_id_field) if user_id_field else ''
                    
                    # 验证用户名和密码
                    if account == username and stored_password == password:
                        logger.info(f"用户 {username} 认证成功")
                        return {
                            "username": username,
                            "user_id": user_id,
                            "record_id": record.record_id
                        }
                
                logger.warning(f"用户 {username} 认证失败")
                return None
                
            except Exception as e:
                error_msg = str(e)
                
                # 检查是否为token相关错误
                if any(code in error_msg for code in ['99991663', '99991664', 'invalid_token', 'token_expired']):
                    logger.warning(f"Token错误: {error_msg}")
                    logger.error("请检查.env文件中的FEISHU_ACCESS_TOKEN是否有效")
                
                logger.error(f"用户认证过程中发生错误: {error_msg}")
                return None
        
        logger.error(f"用户认证失败，已达到最大重试次数")
        return None
    
    def save_voice_log(
        self, 
        content: str, 
        user_id: str, 
        transcription: Optional[str] = None,
        summary: Optional[str] = None
    ) -> bool:
        """
        保存语音日志到多维表格
        
        :param content: 日志内容
        :param user_id: 用户ID
        :param transcription: 语音转录文本（可选）
        :param summary: AI摘要（可选）
        :return: 保存是否成功
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 准备要保存的数据
                log_data = {
                    "日志内容": content,
                    "人员": user_id,
                    "创建时间": int(datetime.now().timestamp() * 1000)  # 毫秒时间戳
                }
                
                # 如果有转录文本，添加到数据中
                if transcription:
                    log_data["转录文本"] = transcription
                
                # 如果有AI摘要，添加到数据中
                if summary:
                    log_data["AI摘要"] = summary
                
                # 创建记录
                result = self.create_records(
                    app_token=self.log_app_token,
                    table_id=self.log_table_id,
                    records_to_create=[log_data]
                )
                
                if result:
                    logger.info(f"成功保存语音日志，记录ID: {result[0].record_id}")
                    return True
                else:
                    logger.error("保存语音日志失败")
                    return False
                    
            except Exception as e:
                error_msg = str(e)
                
                # 检查是否为token相关错误
                if any(code in error_msg for code in ['99991663', '99991664', 'invalid_token', 'token_expired']):
                    logger.warning(f"Token错误: {error_msg}")
                    logger.error("请检查.env文件中的FEISHU_ACCESS_TOKEN是否有效")
                
                logger.error(f"保存语音日志过程中发生错误: {error_msg}")
                return False
        
        logger.error(f"保存语音日志失败，已达到最大重试次数")
        return False


# 全局客户端实例
_feishu_client = None


def get_feishu_client() -> FeishuBitableClient:
    """获取飞书客户端实例（单例模式）"""
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuBitableClient()
    return _feishu_client


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """用户认证（全局函数）
    
    Args:
        username: 用户名
        password: 密码
    """
    client = get_feishu_client()
    return client.authenticate_user(username, password)


def save_voice_log(
    content: str, 
    user_id: str, 
    transcription: Optional[str] = None,
    summary: Optional[str] = None
) -> bool:
    """保存语音日志（全局函数）
    
    Args:
        content: 日志内容
        user_id: 用户ID
        transcription: 转录文本
        summary: 摘要
    """
    client = get_feishu_client()
    return client.save_voice_log(content, user_id, transcription, summary)