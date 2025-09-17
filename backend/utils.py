import os
import json
import requests
import pickle
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import oss2
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
import dashscope
from dashscope import Generation
from oss_optimizer import get_oss_optimizer, upload_file_to_oss_optimized

# 日志目录常量
LOG_DIR = "logs"


def create_common_request(domain: str, version: str, protocol_type: str, method: str, uri: str) -> CommonRequest:
    """
    创建通用请求对象
    
    Args:
        domain (str): API域名
        version (str): API版本
        protocol_type (str): 协议类型
        method (str): 请求方法
        uri (str): URI路径
    
    Returns:
        CommonRequest: 配置好的请求对象
    """
    request = CommonRequest()
    request.set_accept_format('json')
    request.set_domain(domain)
    request.set_version(version)
    request.set_protocol_type(protocol_type)
    request.set_method(method)
    request.set_uri_pattern(uri)
    request.add_header('Content-Type', 'application/json')
    return request


def check_file_exists_in_oss(bucket: oss2.Bucket, object_name: str) -> bool:
    """
    检查文件是否已存在于OSS中
    
    Args:
        bucket: oss2.Bucket对象
        object_name (str): OSS对象名称
    
    Returns:
        bool: 文件是否存在
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        bucket.get_object_meta(object_name)
        return True
    except oss2.exceptions.NoSuchKey:
        # 文件不存在是正常情况，不需要记录错误日志
        return False
    except Exception as e:
        logger.error(f"检查OSS文件是否存在时发生错误: {str(e)}")
        return False


def upload_file_to_oss(file_path: str, use_optimized: bool = True) -> Optional[str]:
    """
    将本地文件上传到OSS并返回可访问的URL
    如果文件已存在，直接返回URL
    
    Args:
        file_path (str): 本地文件路径
        use_optimized (bool): 是否使用优化版本（支持传输加速和断点续传）
    
    Returns:
        str: 文件在OSS上的访问URL，失败时返回None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 优先使用优化版本
    if use_optimized:
        try:
            result = upload_file_to_oss_optimized(file_path)
            if result:
                return result
            else:
                logger.warning("优化版本上传失败，回退到原始版本")
        except Exception as e:
            logger.warning(f"优化版本上传异常，回退到原始版本: {str(e)}")
    
    # 原始版本作为备用方案
    try:
        # 获取环境变量
        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        oss_endpoint = os.getenv('OSS_ENDPOINT')
        oss_bucket_name = os.getenv('OSS_BUCKET_NAME')
        
        if not all([access_key_id, access_key_secret, oss_endpoint, oss_bucket_name]):
            logger.error("缺少必要的OSS配置环境变量")
            return None
        
        logger.info(f"开始处理文件上传（原始版本）: {file_path}")
        
        # 创建 Bucket 实例
        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, oss_endpoint, oss_bucket_name)
        
        # 生成 OSS 对象名称（使用文件名作为唯一标识）
        file_name = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        object_name = f'audio/{timestamp}_{file_name}'
        
        # 检查文件是否已存在
        exists = check_file_exists_in_oss(bucket, object_name)
        if exists:
            logger.info(f"文件 {file_name} 已存在于OSS中")
            # 直接返回文件的URL
            return bucket.sign_url('GET', object_name, 24 * 3600)
            
        # 显示上传进度的回调函数
        last_rate = [0]  # 使用列表来存储上次的进度，避免闭包问题
        def percentage(consumed_bytes, total_bytes):
            if total_bytes and total_bytes > 0:
                rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
                # 每增加10%或达到100%时记录日志，避免重复记录相同进度
                if rate > last_rate[0] and (rate % 10 == 0 or rate == 100):
                    logger.info(f'{file_name} 上传进度: {rate}%')
                    last_rate[0] = rate
            else:
                logger.info(f'{file_name} 上传进度: 处理中...')
        
        # 文件不存在，执行上传
        logger.info(f"开始上传文件 {file_name} 到OSS...")
        with open(file_path, 'rb') as f:
            bucket.put_object(object_name, f, progress_callback=percentage)
        
        # 生成文件 URL（默认有效期24小时）
        url = bucket.sign_url('GET', object_name, 24 * 3600)
        logger.info(f"文件上传成功，URL有效期为24小时")
        return url
        
    except oss2.exceptions.OssError as e:
        logger.error(f"OSS上传失败: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"上传过程发生错误: {str(e)}")
        return None


def init_parameters(file_url: str) -> Dict[str, Any]:
    """
    初始化转写任务的参数
    
    Args:
        file_url (str): 音频文件的URL
    
    Returns:
        dict: 包含所有任务参数的字典
    """
    appkey = os.getenv('APPKEY')
    if not appkey:
        raise ValueError("缺少APPKEY环境变量")
    
    body = dict()
    body['AppKey'] = appkey

    # 基本请求参数
    input_params = dict()
    input_params['SourceLanguage'] = 'cn'
    input_params['TaskKey'] = 'task' + datetime.now().strftime('%Y%m%d%H%M%S')
    input_params['FileUrl'] = file_url
    body['Input'] = input_params

    # AI参数设置
    parameters = dict()
    
    # 语音识别控制
    transcription = dict()
    transcription['DiarizationEnabled'] = True  # 开启角色分离
    diarization = dict()
    diarization['SpeakerCount'] = 2  # 设置说话人数量
    transcription['Diarization'] = diarization
    parameters['Transcription'] = transcription

    # 其他可选参数
    parameters['AutoChaptersEnabled'] = True  # 开启章节速览
    parameters['TextPolishEnabled'] = True    # 开启口语书面化
    parameters['SummaryEnabled'] = True        # 开启智能总结
    parameters['MeetingAssistanceEnabled'] = True  # 开启会议助手

    body['Parameters'] = parameters
    return body


def submit_transcription_task(file_url: str) -> Optional[str]:
    """
    提交音频转写任务
    
    Args:
        file_url (str): 音频文件的URL
    
    Returns:
        str: 任务ID，失败时返回None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"开始提交转录任务，文件URL: {file_url}")
        
        # 初始化任务参数
        body = init_parameters(file_url)
        
        # 获取环境变量
        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        
        if not all([access_key_id, access_key_secret]):
            logger.error("缺少阿里云访问密钥环境变量")
            return None
        
        # 创建客户端
        credentials = AccessKeyCredential(access_key_id, access_key_secret)
        client = AcsClient(region_id='cn-beijing', credential=credentials)

        # 创建并发送请求
        request = create_common_request(
            'tingwu.cn-beijing.aliyuncs.com',
            '2023-09-30',
            'https',
            'PUT',
            '/openapi/tingwu/v2/tasks'
        )
        request.add_query_param('type', 'offline')
        request.set_content(json.dumps(body).encode('utf-8'))
        
        logger.info("发送转录任务请求到阿里云API")
        
        # 发送请求并获取响应
        response = client.do_action_with_exception(request)
        response_dict = json.loads(response)
        
        logger.info("任务提交响应: \n" + json.dumps(response_dict, indent=4, ensure_ascii=False))
        task_id = response_dict.get('Data', {}).get('TaskId')
        
        if task_id:
            logger.info(f"转录任务提交成功，任务ID: {task_id}")
        else:
            logger.error("转录任务提交失败，未获取到任务ID")
            
        return task_id
        
    except Exception as e:
        logger.error(f"提交转写任务失败: {str(e)}")
        return None


def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """
    查询转写任务的状态和结果
    
    Args:
        task_id (str): 任务ID
    
    Returns:
        dict: 任务状态和结果，失败时返回None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 获取环境变量
        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        
        if not all([access_key_id, access_key_secret]):
            logger.error("缺少阿里云访问密钥环境变量")
            return None
        
        logger.info(f"查询阿里云任务状态: {task_id}")
        
        credentials = AccessKeyCredential(access_key_id, access_key_secret)
        client = AcsClient(region_id='cn-beijing', credential=credentials)

        uri = f'/openapi/tingwu/v2/tasks/{task_id}'
        request = create_common_request(
            'tingwu.cn-beijing.aliyuncs.com',
            '2023-09-30',
            'https',
            'GET',
            uri
        )

        response = client.do_action_with_exception(request)
        response_dict = json.loads(response)
        
        logger.info(f"任务状态查询成功: {task_id}, 状态: {response_dict.get('Data', {}).get('TaskStatus', 'Unknown')}")
        return response_dict
        
    except Exception as e:
        logger.error(f"查询任务状态失败 {task_id}: {str(e)}")
        # 返回None而不是抛出异常，避免中断API响应
        return None


def download_and_parse_transcription(transcription_url: str) -> str:
    """
    下载并解析阿里云转录JSON文件，提取转录文本
    
    Args:
        transcription_url (str): 转录文件的URL
    
    Returns:
        str: 提取的转录文本
    """
    import requests
    import logging
    from collections import defaultdict
    
    logger = logging.getLogger(__name__)
    
    try:
        # 下载JSON文件
        response = requests.get(transcription_url, timeout=30)
        response.raise_for_status()
        
        # 解析JSON数据
        data = response.json()
        
        # 获取段落数据
        paragraphs = data.get('Transcription', {}).get('Paragraphs', [])
        
        # 提取所有文本内容
        all_text = []
        
        for para in paragraphs:
            words = para.get('Words', [])
            if words:
                # 提取每个词的文本并连接
                para_text = ''.join([word.get('Text', '') for word in words])
                if para_text.strip():
                    all_text.append(para_text.strip())
        
        # 合并所有文本
        full_text = '\n'.join(all_text)
        
        logger.info(f"成功解析转录文件，提取文本长度: {len(full_text)}")
        return full_text
        
    except Exception as e:
        logger.error(f"下载或解析转录文件失败: {str(e)}")
        return "转录文件解析失败"


def transcribe_audio(file_path: str) -> Optional[str]:
    """
    核心业务流程：上传、转录、获取结果
    
    Args:
        file_path (str): 本地音频文件路径
    
    Returns:
        str: 转录结果文本，失败时返回None
    """
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    try:
        # 1. 上传文件到OSS
        logger.info("开始执行音频转录全流程...")
        file_url = upload_file_to_oss(file_path)
        if not file_url:
            logger.error("文件上传失败，中止转录流程")
            return None
        
        # 2. 提交转录任务
        task_id = submit_transcription_task(file_url)
        if not task_id:
            logger.error("提交转录任务失败，中止流程")
            return None
            
        # 3. 轮询任务结果
        max_retries = 30  # 最大轮询次数
        retry_interval = 120  # 轮询间隔（秒）- 修改为2分钟
        
        for i in range(max_retries):
            logger.info(f"第 {i+1}/{max_retries} 次查询任务状态: {task_id}")
            result = get_task_result(task_id)
            
            if result:
                task_status = result.get('Data', {}).get('TaskStatus')
                
                # 根据官方文档，正确的任务状态处理
                if task_status == 'COMPLETED':
                    logger.info(f"任务 {task_id} 执行成功")
                    # 提取转录结果URL
                    transcription_result = result.get('Data', {}).get('Result', {})
                    transcription_url = transcription_result.get('Transcription')
                    if transcription_url:
                        # 下载并解析转录文本
                        return download_and_parse_transcription(transcription_url)
                    else:
                        logger.error("未找到转录结果URL")
                        return "转录成功，但未找到结果文件URL"
                
                elif task_status == 'FAILED':
                    error_code = result.get('Data', {}).get('ErrorCode', '')
                    error_message = result.get('Data', {}).get('ErrorMessage', '未知错误')
                    logger.error(f"任务 {task_id} 执行失败: [{error_code}] {error_message}")
                    return f"任务处理失败: [{error_code}] {error_message}"
                
                elif task_status == 'INVALID':
                    logger.error(f"任务 {task_id} 无效")
                    return "任务无效，请检查输入参数"
                
                # 如果任务仍在运行，则等待后继续
                elif task_status == 'ONGOING':
                    logger.info(f"任务 {task_id} 仍在处理中，状态: {task_status}，将在 {retry_interval} 秒后重试")
                    time.sleep(retry_interval)
                
                else:
                    logger.warning(f"任务 {task_id} 出现未知状态: {task_status}")
                    time.sleep(retry_interval)
            else:
                logger.error(f"查询任务 {task_id} 状态失败，将在 {retry_interval} 秒后重试")
                time.sleep(retry_interval)

        logger.error(f"任务 {task_id} 超时，轮询 {max_retries} 次后仍未完成")
        return "任务处理超时"
        
    except Exception as e:
        logger.error(f"音频转录全流程发生严重错误: {str(e)}")
        return None


def generate_meeting_summary_prompt(task_type: str = "day_report") -> str:
    """
    生成不同类型的会议纪要提示词
    
    Args:
        task_type (str): 提示词类型，可选值：
            - "day_report": 生成日报
            - "key_points": 仅提取关键点
            - "action_items": 仅提取待办事项
    """
    prompts = {
        "day_report": """# 角色 (Role)
你将扮演我的首席参谋（Chief of Staff）兼数据分析师。你的核心价值在于，不仅能处理信息，更能洞察信息背后的关联、重点与价值。你需要具备极高的精准度、强大的归纳能力和敏锐的商业洞察力。

# 背景与数据输入 (Background & Data Input)
我将为你提供语音记录数据。在处理时，请严格遵守以下规则：

【主要文字稿】: 这可能是单个音频文件的转写结果，也可能是多个音频片段按时间顺序拼接的完整文字稿。每个片段会以【文件名】标识。这是所有分析的主要事实来源（Primary Source of Truth）。

**重要说明：内容识别规则**
- 对于多个音频片段的情况，请将所有片段视为一个连续的工作会话或思考过程
- 分析时要注意片段之间的逻辑关联和时间顺序
- 如果存在发言人标识，发言人1通常是我的真实语音记录，包含有价值的工作内容、决策、想法和行动计划
- 发言人2通常是环境音、噪音或无关内容，应被忽略

# 核心任务指令 (Core Task Directives)
请严格按照以下步骤执行任务：

1. 深度分析与提炼 (In-depth Analysis & Synthesis):
- 主要分析: 彻底解析文字稿内容，如果是多个音频片段拼接，请按【文件名】标识识别不同片段，并将它们作为连续的工作会话进行分析。
- 内容提取: 提取每个片段或对话的核心内容，如果存在发言人标识，重点关注发言人1的内容，忽略发言人2的无关内容。
- 识别主题: 识别出讨论的各个核心议题，注意跨片段的主题连续性和发展脉络。
- 挖掘关键信息: 精准定位关键决策、数据点、思考过程、结论，以及行动计划（Action Items），特别关注片段间的逻辑关联。

2. 生成日报 (Generate Daily Report):
- 目标: 创建一份高度浓缩、逻辑清晰、可供快速回顾的个人工作日报。
- 要求: 报告语言需专业、客观、精炼。避免口语化表达，将思考内容转化为书面工作纪要。

# 输出格式与要求 (Output Format & Requirements)
请严格遵循以下Markdown格式，确保报告结构清晰、信息完整：

【我的日报 - [YYYY-MM-DD]】

一、今日核心概要 (Executive Summary)
[用1-3个要点，高度概括当天最重要的成果、决策或风险。目标是让我用30秒就能了解全天最重要的事。]

二、详细工作纪要 (Detailed Log)
上午 (AM):
[活动/思考 1]: [简述活动背景]。核心思考：[总结思考要点]。最终结论/决策：[明确说明结论]。
[活动/思考 2]: ...

下午 (PM):
[活动/思考 3]: [简述活动背景]。核心思考：[总结思考要点]。最终结论/决策：[明确说明结论]。
...

其他关键想法 (Other Key Insights):
[记录未包含在主要活动中，但同样重要的零散思考或灵感]。

三、待办事项清单 (Action Items)
[任务1]: [明确的任务描述]。责任人：我。截止日期：[如提及]。
[任务2]: [明确的任务描述]。责任人：我。截止日期：[如提及]。
...

**重要提醒：请确保所有分析和结论都主要基于文字稿中发言人1的内容，发言人2的内容应被忽略。**""",

        "key_points": """请以首席参谋的视角分析语音记录，提取以下关键信息：

**重要说明：主要分析文字稿中发言人1的内容，发言人2的内容应被忽略。**

1. 各个议题的核心思考要点和商业洞察
2. 重要决策和结论及其潜在影响
3. 风险点或需要特别关注的战略问题
4. 关键数据点和业务指标

请按时间顺序组织内容，并标注具体的时间点。语言需专业、客观、精炼。""",

        "action_items": """请以首席参谋的精准度仔细分析语音记录，列出所有明确的个人任务：

**重要说明：主要分析文字稿中发言人1的内容，发言人2的内容应被忽略。**

1. 任务具体内容（避免口语化表达）
2. 责任人（通常是我本人）
3. 截止日期（如有提及）
4. 相关依赖或注意事项
5. 优先级评估

请按紧急程度和重要性排序，确保每项任务描述清晰、可执行。""",

        "brief": "请对以下文本生成一个简洁的摘要，突出主要内容和关键信息：",
        "detailed": "请对以下文本生成一个详细的摘要，包含主要观点、关键细节和重要结论："
    }
    
    return prompts.get(task_type, prompts["day_report"])

def get_summary(text: str, summary_type: str = "brief") -> str:
    """
    使用阿里云通义千问qwen-plus模型生成文本摘要
    
    Args:
        text (str): 要摘要的文本
        summary_type (str): 摘要类型 (brief, detailed, key_points, day_report, action_items)
    
    Returns:
        str: 生成的摘要文本
    """
    from http import HTTPStatus
    import time
    
    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope_api_key:
        return f"文本摘要（长度: {len(text)}字符）: {text[:200]}..."
    
    # 重试机制
    max_retries = 3
    retry_delay = 1  # 秒
    
    for attempt in range(max_retries):
        try:
            # 使用原生dashscope库
            dashscope.api_key = dashscope_api_key
            
            # 根据摘要类型选择提示词
            if summary_type in ["day_report", "key_points", "action_items"]:
                # 使用详细的会议纪要提示词
                prompt = generate_meeting_summary_prompt(summary_type)
                full_prompt = f"{prompt}\n\n{text}"
            else:
                # 使用简单的摘要提示词
                simple_prompts = {
                    "brief": "请对以下文本生成一个简洁的摘要，突出主要内容和关键信息：",
                    "detailed": "请对以下文本生成一个详细的摘要，包含主要观点、关键细节和重要结论："
                }
                prompt = simple_prompts.get(summary_type, simple_prompts["brief"])
                full_prompt = f"{prompt}\n\n{text}"
            
            # 调用通义千问API - 使用正确的消息格式
            response = Generation.call(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": "你是一位专业的首席参谋和数据分析师，具备极高的精准度、强大的归纳能力和敏锐的商业洞察力。"},
                    {"role": "user", "content": full_prompt}
                ],
                result_format='message',
                max_tokens=2000,
                temperature=0.7
            )
            
            # 使用HTTPStatus检查状态码
            if response.status_code == HTTPStatus.OK:
                summary = response.output.choices[0]['message']['content']
                return summary
            else:
                error_msg = f"API调用失败 - 状态码: {response.status_code}, 错误代码: {response.code}, 错误信息: {response.message}"
                if attempt < max_retries - 1:
                    print(f"第{attempt + 1}次尝试失败，{retry_delay}秒后重试: {error_msg}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    continue
                else:
                    return f"摘要生成失败: {error_msg}，原文长度: {len(text)}字符"
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                print(f"第{attempt + 1}次尝试异常，{retry_delay}秒后重试: {error_msg}")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
                continue
            else:
                return f"摘要生成失败: {error_msg}，原文长度: {len(text)}字符"
    
    return f"摘要生成失败: 重试{max_retries}次后仍然失败，原文长度: {len(text)}字符"


def load_and_index_logs():
    """
    加载并索引日志文件
    
    Returns:
        tuple: (index, documents) - 索引对象和文档列表
    """
    logs = []
    logger = logging.getLogger(__name__)
    
    try:
        if not os.path.exists(LOG_DIR):
            logger.info(f"日志目录 {LOG_DIR} 不存在")
            return None, logs
            
        for filename in os.listdir(LOG_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(LOG_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        log_data = json.load(f)
                        logs.append(log_data)
                except Exception as e:
                    logger.error(f"读取日志文件 {filename} 失败: {str(e)}")
                    
        # 按时间戳排序
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        logger.info(f"成功加载 {len(logs)} 条日志记录")
        
    except Exception as e:
        logger.error(f"加载日志失败: {str(e)}")
        
    # 返回简单的索引（这里可以是None或简单的字典）和文档列表
    return None, logs


def query_logs(query: str, logs: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    查询日志记录
    
    Args:
        query (str): 查询关键词
        logs (List[Dict[str, Any]], optional): 日志列表，如果为None则重新加载
    
    Returns:
        List[Dict[str, Any]]: 匹配的日志记录
    """
    if logs is None:
        logs = load_and_index_logs()
    
    if not query:
        return logs
    
    query_lower = query.lower()
    filtered_logs = []
    
    for log in logs:
        # 在多个字段中搜索
        searchable_text = " ".join([
            str(log.get('filename', '')),
            str(log.get('transcription', '')),
            str(log.get('summary', '')),
            str(log.get('status', ''))
        ]).lower()
        
        if query_lower in searchable_text:
            filtered_logs.append(log)
    
    return filtered_logs


def get_latest_log_summary(limit: int = 5) -> str:
    """
    获取最新日志的摘要
    
    Args:
        limit (int): 返回的日志数量限制
    
    Returns:
        str: 日志摘要文本
    """
    logs = load_and_index_logs()
    
    if not logs:
        return "暂无日志记录"
    
    recent_logs = logs[:limit]
    summary_parts = []
    
    for i, log in enumerate(recent_logs, 1):
        timestamp = log.get('timestamp', '未知时间')
        filename = log.get('filename', '未知文件')
        status = log.get('status', '未知状态')
        
        summary_parts.append(f"{i}. {timestamp} - {filename} ({status})")
        
        if log.get('summary'):
            summary_parts.append(f"   摘要: {log['summary'][:100]}...")
    
    return "\n".join(summary_parts)


def generate_capability_assessment(text: str, user_context: str = "") -> str:
    """
    基于用户的语音日志内容生成个人能力评估
    
    Args:
        text (str): 要分析的文本内容
        user_context (str): 用户上下文信息（可选）
    
    Returns:
        str: 生成的个人能力评估文本
    """
    from http import HTTPStatus
    import time
    
    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope_api_key:
        return f"个人能力评估（基于{len(text)}字符内容）: 暂无AI分析，请配置DASHSCOPE_API_KEY"
    
    # 重试机制
    max_retries = 3
    retry_delay = 1  # 秒
    
    for attempt in range(max_retries):
        try:
            # 使用原生dashscope库
            dashscope.api_key = dashscope_api_key
            
            # 个人能力评估的专用提示词
            capability_prompt = """
你是一位专业的人力资源分析师和职业发展顾问。请基于以下用户的工作日志内容，从多个维度分析其个人能力表现，并提供建设性的评估和建议。

请从以下几个维度进行分析：
1. **专业技能**: 技术能力、专业知识掌握程度
2. **沟通协作**: 团队合作、沟通表达能力
3. **问题解决**: 分析问题、解决问题的能力
4. **学习成长**: 学习新知识、适应变化的能力
5. **执行力**: 任务完成效率、目标达成情况
6. **创新思维**: 创新意识、改进优化能力

评估格式要求：
- 每个维度给出具体的表现描述和评分（1-5分）
- 指出优势和待改进的地方
- 提供具体的改进建议
- 总体评估不超过300字

请基于以下内容进行分析：
"""
            
            full_prompt = f"{capability_prompt}\n\n{text}"
            if user_context:
                full_prompt += f"\n\n用户背景信息：{user_context}"
            
            response = dashscope.Generation.call(
                model="qwen-plus",
                prompt=full_prompt,
                max_tokens=800,  # 适当增加token数以支持详细评估
                temperature=0.7,  # 适中的创造性
                top_p=0.8
            )
            
            if response.status_code == HTTPStatus.OK:
                capability_assessment = response.output.text.strip()
                if capability_assessment:
                    return capability_assessment
                else:
                    return f"个人能力评估生成失败: 返回内容为空，原文长度: {len(text)}字符"
            else:
                error_msg = f"API调用失败，状态码: {response.status_code}"
                if hasattr(response, 'message'):
                    error_msg += f"，错误信息: {response.message}"
                
                if attempt < max_retries - 1:
                    print(f"第{attempt + 1}次尝试失败，{retry_delay}秒后重试: {error_msg}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    continue
                else:
                    return f"个人能力评估生成失败: {error_msg}，原文长度: {len(text)}字符"
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                print(f"第{attempt + 1}次尝试异常，{retry_delay}秒后重试: {error_msg}")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
                continue
            else:
                return f"个人能力评估生成失败: {error_msg}，原文长度: {len(text)}字符"
    
    return f"个人能力评估生成失败: 重试{max_retries}次后仍然失败，原文长度: {len(text)}字符"


# 音频处理相关函数
def concatenate_audio_with_master_voice(audio_file_path: str, master_voice_path: str, output_path: str) -> bool:
    """
    将主人声音频与目标音频拼接
    
    Args:
        audio_file_path (str): 原始音频文件路径
        master_voice_path (str): 主人声音频文件路径
        output_path (str): 输出文件路径
    
    Returns:
        bool: 拼接是否成功
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(master_voice_path):
            logging.error(f"主人声文件不存在: {master_voice_path}")
            return False
            
        if not os.path.exists(audio_file_path):
            logging.error(f"目标音频文件不存在: {audio_file_path}")
            return False
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logging.info(f"创建输出目录: {output_dir}")
        
        # 检查文件格式并选择合适的处理方式
        audio_is_wav = audio_file_path.lower().endswith('.wav')
        audio_is_mp3 = audio_file_path.lower().endswith('.mp3')
        master_is_wav = master_voice_path.lower().endswith('.wav')
        master_is_mp3 = master_voice_path.lower().endswith('.mp3')
        
        logging.info(f"音频格式检测 - 目标音频: {'WAV' if audio_is_wav else 'MP3' if audio_is_mp3 else '未知'}, 主人声: {'WAV' if master_is_wav else 'MP3' if master_is_mp3 else '未知'}")
        
        # 如果两个文件都是WAV格式，或者目标音频是WAV格式，优先使用wave库
        if audio_is_wav:
            try:
                import wave
                import struct
                
                logging.info("使用 wave 库进行音频拼接")
                
                # 如果主人声是 MP3，先尝试用 pydub 转换
                temp_master_wav = None
                if master_voice_path.lower().endswith('.mp3'):
                    try:
                        from pydub import AudioSegment
                        master_audio = AudioSegment.from_mp3(master_voice_path)
                        # 限制为5秒
                        if len(master_audio) > 5000:
                            master_audio = master_audio[:5000]
                        
                        temp_master_wav = output_path.replace('.wav', '_temp_master.wav')
                        master_audio.export(temp_master_wav, format="wav")
                        master_voice_path = temp_master_wav
                        logging.info(f"MP3 主人声转换为 WAV: {temp_master_wav}")
                    except ImportError:
                        logging.warning("无法转换 MP3 主人声，创建简单提示音")
                        # 创建一个简单的提示音（1秒，440Hz 正弦波）
                        import math
                        sample_rate = 44100
                        duration = 1.0  # 1秒
                        frequency = 440  # A4音符
                        
                        temp_master_wav = output_path.replace('.wav', '_temp_beep.wav')
                        
                        # 先读取目标音频参数以匹配格式
                        with wave.open(audio_file_path, 'rb') as target_wav:
                            target_params = target_wav.getparams()
                        
                        with wave.open(temp_master_wav, 'wb') as beep_wav:
                            beep_wav.setnchannels(target_params.nchannels)  # 匹配目标声道数
                            beep_wav.setsampwidth(target_params.sampwidth)  # 匹配目标采样宽度
                            beep_wav.setframerate(target_params.framerate)  # 匹配目标采样率
                            
                            # 生成正弦波数据（匹配目标格式）
                            frames = []
                            for i in range(int(target_params.framerate * duration)):
                                value = int(16384 * math.sin(2 * math.pi * frequency * i / target_params.framerate))
                                # 如果是立体声，复制到所有声道
                                frame_data = struct.pack('<h', value) * target_params.nchannels
                                frames.append(frame_data)
                            
                            beep_wav.writeframes(b''.join(frames))
                        
                        master_voice_path = temp_master_wav
                        logging.info(f"创建提示音替代主人声: {temp_master_wav}")
                
                # 读取主人声 WAV 文件
                with wave.open(master_voice_path, 'rb') as master_wav:
                    master_params = master_wav.getparams()
                    master_frames = master_wav.readframes(master_params.nframes)
                
                # 读取目标 WAV 文件
                with wave.open(audio_file_path, 'rb') as target_wav:
                    target_params = target_wav.getparams()
                    target_frames = target_wav.readframes(target_params.nframes)
                
                # 创建静音（0.5秒）
                silence_frames_count = int(target_params.framerate * 0.5)  # 0.5秒
                silence_frame = struct.pack('<h', 0) * target_params.nchannels
                silence_frames = silence_frame * silence_frames_count
                
                # 写入拼接后的音频
                with wave.open(output_path, 'wb') as output_wav:
                    output_wav.setparams(target_params)
                    
                    # 写入主人声（如果采样率匹配）
                    if master_params.framerate == target_params.framerate and master_params.nchannels == target_params.nchannels:
                        output_wav.writeframes(master_frames)
                    else:
                        logging.warning(f"主人声参数不匹配 (采样率: {master_params.framerate} vs {target_params.framerate}, 声道: {master_params.nchannels} vs {target_params.nchannels})，跳过主人声")
                    
                    # 写入静音
                    output_wav.writeframes(silence_frames)
                    
                    # 写入目标音频
                    output_wav.writeframes(target_frames)
                
                # 清理临时文件
                if temp_master_wav and os.path.exists(temp_master_wav):
                    os.remove(temp_master_wav)
                
                # 验证输出文件
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    logging.info(f"音频拼接成功 (wave): {output_path} (大小: {output_size} bytes)")
                    return True
                else:
                    logging.error(f"输出文件未生成: {output_path}")
                    return False
                    
            except Exception as wave_error:
                logging.error(f"wave 库拼接失败: {wave_error}")
        
        # 如果目标音频是MP3格式，或者wave库处理失败，使用pydub处理
        logging.info("使用 pydub 进行音频拼接")
        try:
            from pydub import AudioSegment
            from pydub.utils import which
            
            # 检查是否有ffmpeg
            ffmpeg_path = which("ffmpeg")
            if not ffmpeg_path:
                logging.warning("未找到ffmpeg，pydub功能可能受限")
            
            # 加载音频文件
            logging.info(f"加载主人声文件: {master_voice_path}")
            try:
                master_voice = AudioSegment.from_file(master_voice_path)
                logging.info(f"主人声音频长度: {len(master_voice)}ms")
            except Exception as load_error:
                logging.error(f"加载主人声文件失败: {load_error}")
                raise load_error
            
            logging.info(f"加载目标音频文件: {audio_file_path}")
            try:
                target_audio = AudioSegment.from_file(audio_file_path)
                logging.info(f"目标音频长度: {len(target_audio)}ms")
            except Exception as load_error:
                logging.error(f"加载目标音频文件失败: {load_error}")
                raise load_error
            
            # 确保主人声音频不超过5秒（避免过长影响转写效果）
            if len(master_voice) > 5000:  # 5秒 = 5000毫秒
                logging.info(f"主人声音频过长({len(master_voice)}ms)，截取前5秒")
                master_voice = master_voice[:5000]
            
            # 在主人声和目标音频之间添加短暂的静音（0.5秒）
            silence = AudioSegment.silent(duration=500)  # 0.5秒静音
            logging.info("添加0.5秒静音间隔")
            
            # 拼接音频：主人声 + 静音 + 目标音频
            combined_audio = master_voice + silence + target_audio
            logging.info(f"拼接后音频总长度: {len(combined_audio)}ms")
            
            # 导出拼接后的音频
            logging.info(f"导出拼接后的音频到: {output_path}")
            
            # 根据输出路径确定格式
            output_format = "wav" if output_path.lower().endswith('.wav') else "mp3"
            
            try:
                combined_audio.export(output_path, format=output_format)
                logging.info(f"音频导出成功，格式: {output_format}")
            except Exception as export_error:
                logging.error(f"音频导出失败: {export_error}")
                # 如果导出失败，尝试使用原始格式
                if output_format == "wav":
                    logging.info("尝试导出为MP3格式")
                    mp3_output = output_path.replace('.wav', '.mp3')
                    combined_audio.export(mp3_output, format="mp3")
                    # 重命名为原始输出路径
                    import shutil
                    shutil.move(mp3_output, output_path)
                    logging.info(f"已导出为MP3并重命名: {output_path}")
                else:
                    raise export_error
            
            # 验证输出文件
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logging.info(f"音频拼接成功 (pydub): {output_path} (大小: {output_size} bytes)")
                return True
            else:
                logging.error(f"输出文件未生成: {output_path}")
                return False
                
        except ImportError as import_error:
            logging.error(f"pydub库导入失败: {import_error}")
            logging.info("使用简化的MP3拼接方案")
            
            # 简化的MP3拼接方案：二进制文件拼接
            try:
                import shutil
                
                # 检查文件格式
                if audio_file_path.lower().endswith('.mp3') and master_voice_path.lower().endswith('.mp3'):
                    logging.info("执行MP3+MP3二进制拼接")
                    
                    # 读取主人声MP3文件（限制大小，避免过大）
                    master_data = b''
                    master_size = os.path.getsize(master_voice_path)
                    max_master_size = 500 * 1024  # 限制主人声文件最大500KB
                    
                    with open(master_voice_path, 'rb') as master_file:
                        if master_size > max_master_size:
                            logging.info(f"主人声文件过大({master_size} bytes)，截取前{max_master_size} bytes")
                            master_data = master_file.read(max_master_size)
                        else:
                            master_data = master_file.read()
                    
                    # 读取目标音频MP3文件
                    with open(audio_file_path, 'rb') as target_file:
                        target_data = target_file.read()
                    
                    # 创建静音数据（简单的零字节序列）
                    silence_data = b'\x00' * 8192  # 8KB的静音数据
                    
                    # 拼接：主人声 + 静音 + 目标音频
                    combined_data = master_data + silence_data + target_data
                    
                    # 写入输出文件
                    with open(output_path, 'wb') as output_file:
                        output_file.write(combined_data)
                    
                    # 验证输出文件
                    if os.path.exists(output_path):
                        output_size = os.path.getsize(output_path)
                        original_size = os.path.getsize(audio_file_path)
                        master_used_size = len(master_data)
                        
                        logging.info(f"MP3二进制拼接成功: {output_path}")
                        logging.info(f"  原始目标文件: {original_size} bytes")
                        logging.info(f"  使用的主人声: {master_used_size} bytes")
                        logging.info(f"  输出文件大小: {output_size} bytes")
                        logging.info(f"  大小增加: {output_size - original_size} bytes")
                        logging.warning("注意：这是简化的二进制拼接，输出文件可能无法正常播放")
                        logging.info("建议安装完整的音频处理库以获得更好的效果")
                        return True
                    else:
                        logging.error(f"输出文件未生成: {output_path}")
                        return False
                        
                elif audio_file_path.lower().endswith('.mp3'):
                    # 如果只有目标音频是MP3，简单复制
                    logging.info("目标音频为MP3，主人声非MP3，执行简单复制")
                    shutil.copy2(audio_file_path, output_path)
                    
                    if os.path.exists(output_path):
                        output_size = os.path.getsize(output_path)
                        logging.info(f"音频处理完成 (复制MP3): {output_path} (大小: {output_size} bytes)")
                        logging.info("注意：由于格式不匹配，未能拼接主人声")
                        return True
                    else:
                        logging.error(f"输出文件未生成: {output_path}")
                        return False
                else:
                    # 如果目标音频是WAV，直接复制
                    logging.info("目标音频为WAV，执行简单复制")
                    shutil.copy2(audio_file_path, output_path)
                    
                    if os.path.exists(output_path):
                        output_size = os.path.getsize(output_path)
                        logging.info(f"音频处理完成 (复制WAV): {output_path} (大小: {output_size} bytes)")
                        return True
                    else:
                        logging.error(f"输出文件未生成: {output_path}")
                        return False
                        
            except Exception as simple_error:
                logging.error(f"简化处理方案失败: {simple_error}")
                logging.error("无法进行音频拼接，所有方法都失败了")
                return False
        
    except Exception as e:
        logging.error(f"音频拼接失败: {e}")
        return False


def get_master_voice_path(user_id: str) -> Optional[str]:
    """
    获取用户的主人声音频文件路径
    
    Args:
        user_id (str): 用户ID
    
    Returns:
        Optional[str]: 主人声音频文件路径，如果不存在则返回None
    """
    master_voice_dir = "master_voices"
    audio_extensions = ['.wav', '.mp3', '.m4a', '.flac']
    
    for ext in audio_extensions:
        potential_file = os.path.join(master_voice_dir, f"{user_id}{ext}")
        if os.path.exists(potential_file):
            return potential_file
    
    return None


def prepare_audio_with_master_voice(audio_file_path: str, user_id: str, temp_dir: str = "temp_processed") -> Optional[str]:
    """
    为音频文件添加主人声前缀，如果用户有主人声样本的话
    
    Args:
        audio_file_path (str): 原始音频文件路径
        user_id (str): 用户ID
        temp_dir (str): 临时文件目录
    
    Returns:
        Optional[str]: 处理后的音频文件路径，如果处理失败或无主人声样本则返回原路径
    """
    try:
        # 检查用户是否有主人声样本
        master_voice_path = get_master_voice_path(user_id)
        if not master_voice_path:
            logging.info(f"用户 {user_id} 未上传主人声样本，跳过音频预处理")
            return audio_file_path
        
        # 创建临时处理目录
        os.makedirs(temp_dir, exist_ok=True)
        
        # 生成输出文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(audio_file_path)
        name, ext = os.path.splitext(filename)
        output_filename = f"processed_{timestamp}_{name}.wav"
        output_path = os.path.join(temp_dir, output_filename)
        
        # 执行音频拼接
        if concatenate_audio_with_master_voice(audio_file_path, master_voice_path, output_path):
            logging.info(f"音频预处理成功: {output_path}")
            return output_path
        else:
            logging.warning(f"音频预处理失败，使用原始文件: {audio_file_path}")
            return audio_file_path
            
    except Exception as e:
        logging.error(f"音频预处理过程中发生错误: {e}")
        return audio_file_path


def cleanup_processed_audio(file_path: str) -> None:
    """
    清理处理后的临时音频文件
    
    Args:
        file_path (str): 要清理的文件路径
    """
    try:
        if file_path and os.path.exists(file_path) and "temp_processed" in file_path:
            os.remove(file_path)
            logging.info(f"清理临时音频文件: {file_path}")
    except Exception as e:
        logging.warning(f"清理临时音频文件失败: {e}")