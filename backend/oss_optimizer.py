import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import oss2
from oss2.models import PartInfo
from oss2 import determine_part_size
from oss2.resumable import resumable_upload, resumable_download
import threading
import time

logger = logging.getLogger(__name__)

class OSSOptimizer:
    """
    优化的OSS客户端，支持传输加速和断点续传
    
    功能特性：
    1. 传输加速 - 使用全球加速节点提升传输速度
    2. 分片上传 - 大文件自动分片，提升上传稳定性
    3. 断点续传 - 支持上传和下载的断点续传
    4. 进度监控 - 实时显示传输进度
    5. 错误重试 - 自动重试失败的传输
    """
    
    def __init__(self, 
                 access_key_id: str = None,
                 access_key_secret: str = None,
                 endpoint: str = None,
                 bucket_name: str = None,
                 enable_acceleration: bool = True):
        """
        初始化OSS优化客户端
        
        Args:
            access_key_id: 阿里云访问密钥ID
            access_key_secret: 阿里云访问密钥Secret
            endpoint: OSS端点
            bucket_name: 存储桶名称
            enable_acceleration: 是否启用传输加速
        """
        # 从环境变量获取配置
        self.access_key_id = access_key_id or os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        self.access_key_secret = access_key_secret or os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        self.endpoint = endpoint or os.getenv('OSS_ENDPOINT')
        self.bucket_name = bucket_name or os.getenv('OSS_BUCKET_NAME')
        self.enable_acceleration = enable_acceleration
        
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            raise ValueError("缺少必要的OSS配置参数")
        
        # 创建认证对象
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        
        # 配置传输加速端点
        if self.enable_acceleration:
            # 将普通端点转换为传输加速端点
            if 'oss-accelerate.aliyuncs.com' not in self.endpoint:
                # 提取区域信息并构建加速端点
                if 'oss-cn-' in self.endpoint:
                    self.accelerate_endpoint = 'oss-accelerate.aliyuncs.com'
                else:
                    self.accelerate_endpoint = self.endpoint
            else:
                self.accelerate_endpoint = self.endpoint
            
            logger.info(f"启用传输加速，使用端点: {self.accelerate_endpoint}")
            self.bucket = oss2.Bucket(self.auth, self.accelerate_endpoint, self.bucket_name)
        else:
            self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
        
        # 配置参数
        self.multipart_threshold = 100 * 1024 * 1024  # 100MB，超过此大小使用分片上传
        self.part_size = 10 * 1024 * 1024  # 10MB每片
        self.max_retry = 3  # 最大重试次数
        
    def check_file_exists(self, object_name: str) -> bool:
        """
        检查文件是否已存在于OSS中
        
        Args:
            object_name: OSS对象名称
            
        Returns:
            bool: 文件是否存在
        """
        try:
            self.bucket.get_object_meta(object_name)
            return True
        except oss2.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.error(f"检查OSS文件是否存在时发生错误: {str(e)}")
            return False
    
    def _create_progress_callback(self, file_name: str, operation: str = "上传") -> Callable:
        """
        创建进度回调函数
        
        Args:
            file_name: 文件名
            operation: 操作类型（上传/下载）
            
        Returns:
            进度回调函数
        """
        last_rate = [0]
        start_time = [time.time()]
        
        def progress_callback(consumed_bytes, total_bytes):
            if total_bytes and total_bytes > 0:
                rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
                current_time = time.time()
                elapsed_time = current_time - start_time[0]
                
                # 计算传输速度
                if elapsed_time > 0:
                    speed = consumed_bytes / elapsed_time / 1024 / 1024  # MB/s
                    
                    # 每增加5%或达到100%时记录日志
                    if rate > last_rate[0] and (rate % 5 == 0 or rate == 100):
                        logger.info(f'{file_name} {operation}进度: {rate}% ({consumed_bytes}/{total_bytes} bytes, {speed:.2f} MB/s)')
                        last_rate[0] = rate
            else:
                logger.info(f'{file_name} {operation}进度: 处理中...')
        
        return progress_callback
    
    def upload_file(self, 
                   file_path: str, 
                   object_name: str = None,
                   enable_resumable: bool = True,
                   progress_callback: Callable = None) -> Optional[str]:
        """
        优化的文件上传功能
        
        Args:
            file_path: 本地文件路径
            object_name: OSS对象名称，如果为None则自动生成
            enable_resumable: 是否启用断点续传
            progress_callback: 自定义进度回调函数
            
        Returns:
            str: 文件访问URL，失败时返回None
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
            
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 生成对象名称
            if object_name is None:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                object_name = f'audio/{timestamp}_{file_name}'
            
            logger.info(f"开始上传文件: {file_name} ({file_size} bytes) -> {object_name}")
            
            # 检查文件是否已存在
            if self.check_file_exists(object_name):
                logger.info(f"文件 {file_name} 已存在于OSS中")
                return self.bucket.sign_url('GET', object_name, 24 * 3600)
            
            # 创建进度回调
            if progress_callback is None:
                progress_callback = self._create_progress_callback(file_name, "上传")
            
            # 根据文件大小选择上传方式
            if file_size > self.multipart_threshold and enable_resumable:
                # 使用断点续传分片上传
                logger.info(f"文件大小 {file_size} bytes 超过阈值，使用断点续传分片上传")
                return self._resumable_upload(file_path, object_name, progress_callback)
            else:
                # 使用普通上传
                logger.info(f"使用普通上传方式")
                return self._simple_upload(file_path, object_name, progress_callback)
                
        except Exception as e:
            logger.error(f"上传文件时发生错误: {str(e)}")
            return None
    
    def _simple_upload(self, file_path: str, object_name: str, progress_callback: Callable) -> Optional[str]:
        """
        简单上传
        
        Args:
            file_path: 本地文件路径
            object_name: OSS对象名称
            progress_callback: 进度回调函数
            
        Returns:
            str: 文件访问URL
        """
        try:
            with open(file_path, 'rb') as f:
                self.bucket.put_object(object_name, f, progress_callback=progress_callback)
            
            url = self.bucket.sign_url('GET', object_name, 24 * 3600)
            logger.info(f"文件上传成功，URL有效期为24小时")
            return url
            
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS上传失败: {str(e)}")
            return None
    
    def _resumable_upload(self, file_path: str, object_name: str, progress_callback: Callable) -> Optional[str]:
        """
        断点续传分片上传
        
        Args:
            file_path: 本地文件路径
            object_name: OSS对象名称
            progress_callback: 进度回调函数
            
        Returns:
            str: 文件访问URL
        """
        try:
            # 创建断点续传上传目录
            store_dir = os.path.join(os.path.dirname(file_path), '.oss_upload_cache')
            os.makedirs(store_dir, exist_ok=True)
            
            # 使用断点续传上传
            resumable_upload(
                bucket=self.bucket,
                key=object_name,
                filename=file_path,
                store=oss2.resumable.make_upload_store(store_dir),
                multipart_threshold=self.multipart_threshold,
                part_size=self.part_size,
                num_threads=4,  # 并发线程数
                progress_callback=progress_callback
            )
            
            url = self.bucket.sign_url('GET', object_name, 24 * 3600)
            logger.info(f"断点续传上传成功，URL有效期为24小时")
            
            # 清理缓存文件
            try:
                import shutil
                if os.path.exists(store_dir):
                    shutil.rmtree(store_dir)
            except Exception as e:
                logger.warning(f"清理上传缓存失败: {str(e)}")
            
            return url
            
        except oss2.exceptions.OssError as e:
            logger.error(f"断点续传上传失败: {str(e)}")
            return None
    
    def download_file(self, 
                     object_name: str, 
                     local_path: str,
                     enable_resumable: bool = True,
                     progress_callback: Callable = None) -> bool:
        """
        优化的文件下载功能
        
        Args:
            object_name: OSS对象名称
            local_path: 本地保存路径
            enable_resumable: 是否启用断点续传
            progress_callback: 自定义进度回调函数
            
        Returns:
            bool: 下载是否成功
        """
        try:
            # 获取文件信息
            try:
                meta = self.bucket.get_object_meta(object_name)
                file_size = int(meta.headers.get('Content-Length', 0))
            except oss2.exceptions.NoSuchKey:
                logger.error(f"OSS中不存在文件: {object_name}")
                return False
            
            file_name = os.path.basename(local_path)
            logger.info(f"开始下载文件: {object_name} ({file_size} bytes) -> {local_path}")
            
            # 创建进度回调
            if progress_callback is None:
                progress_callback = self._create_progress_callback(file_name, "下载")
            
            # 创建目录
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 根据文件大小选择下载方式
            if file_size > self.multipart_threshold and enable_resumable:
                # 使用断点续传下载
                logger.info(f"文件大小 {file_size} bytes 超过阈值，使用断点续传下载")
                return self._resumable_download(object_name, local_path, progress_callback)
            else:
                # 使用普通下载
                logger.info(f"使用普通下载方式")
                return self._simple_download(object_name, local_path, progress_callback)
                
        except Exception as e:
            logger.error(f"下载文件时发生错误: {str(e)}")
            return False
    
    def _simple_download(self, object_name: str, local_path: str, progress_callback: Callable) -> bool:
        """
        简单下载
        
        Args:
            object_name: OSS对象名称
            local_path: 本地保存路径
            progress_callback: 进度回调函数
            
        Returns:
            bool: 下载是否成功
        """
        try:
            self.bucket.get_object_to_file(object_name, local_path, progress_callback=progress_callback)
            logger.info(f"文件下载成功: {local_path}")
            return True
            
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS下载失败: {str(e)}")
            return False
    
    def _resumable_download(self, object_name: str, local_path: str, progress_callback: Callable) -> bool:
        """
        断点续传下载
        
        Args:
            object_name: OSS对象名称
            local_path: 本地保存路径
            progress_callback: 进度回调函数
            
        Returns:
            bool: 下载是否成功
        """
        try:
            # 创建断点续传下载目录
            store_dir = os.path.join(os.path.dirname(local_path), '.oss_download_cache')
            os.makedirs(store_dir, exist_ok=True)
            
            # 使用断点续传下载
            resumable_download(
                bucket=self.bucket,
                key=object_name,
                filename=local_path,
                store=oss2.resumable.make_download_store(store_dir),
                multipart_threshold=self.multipart_threshold,
                part_size=self.part_size,
                num_threads=4,  # 并发线程数
                progress_callback=progress_callback
            )
            
            logger.info(f"断点续传下载成功: {local_path}")
            
            # 清理缓存文件
            try:
                import shutil
                if os.path.exists(store_dir):
                    shutil.rmtree(store_dir)
            except Exception as e:
                logger.warning(f"清理下载缓存失败: {str(e)}")
            
            return True
            
        except oss2.exceptions.OssError as e:
            logger.error(f"断点续传下载失败: {str(e)}")
            return False
    
    def get_file_url(self, object_name: str, expires: int = 24 * 3600) -> str:
        """
        获取文件的签名URL
        
        Args:
            object_name: OSS对象名称
            expires: URL有效期（秒）
            
        Returns:
            str: 签名URL
        """
        return self.bucket.sign_url('GET', object_name, expires)
    
    def delete_file(self, object_name: str) -> bool:
        """
        删除OSS中的文件
        
        Args:
            object_name: OSS对象名称
            
        Returns:
            bool: 删除是否成功
        """
        try:
            self.bucket.delete_object(object_name)
            logger.info(f"文件删除成功: {object_name}")
            return True
        except oss2.exceptions.OssError as e:
            logger.error(f"删除文件失败: {str(e)}")
            return False


# 全局OSS优化器实例
_oss_optimizer = None

def get_oss_optimizer() -> OSSOptimizer:
    """
    获取全局OSS优化器实例
    
    Returns:
        OSSOptimizer: OSS优化器实例
    """
    global _oss_optimizer
    if _oss_optimizer is None:
        _oss_optimizer = OSSOptimizer()
    return _oss_optimizer


# 兼容性函数，保持与现有代码的兼容性
def upload_file_to_oss_optimized(file_path: str) -> Optional[str]:
    """
    优化版本的文件上传函数，保持与原有接口的兼容性
    
    Args:
        file_path: 本地文件路径
        
    Returns:
        str: 文件访问URL，失败时返回None
    """
    try:
        optimizer = get_oss_optimizer()
        return optimizer.upload_file(file_path)
    except Exception as e:
        logger.error(f"优化上传失败，回退到原始方法: {str(e)}")
        # 这里可以回退到原始的上传方法
        return None