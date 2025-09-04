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
    try:
        bucket.get_object_meta(object_name)
        return True
    except oss2.exceptions.NoSuchKey:
        return False
    except Exception as e:
        print(f"检查文件是否存在时发生错误: {str(e)}")
        return False


def upload_file_to_oss(file_path: str) -> Optional[str]:
    """
    将本地文件上传到OSS并返回可访问的URL
    如果文件已存在，直接返回URL
    
    Args:
        file_path (str): 本地文件路径
    
    Returns:
        str: 文件在OSS上的访问URL，失败时返回None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 获取环境变量
        access_key_id = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
        oss_endpoint = os.getenv('OSS_ENDPOINT')
        oss_bucket_name = os.getenv('OSS_BUCKET_NAME')
        
        if not all([access_key_id, access_key_secret, oss_endpoint, oss_bucket_name]):
            logger.error("缺少必要的OSS配置环境变量")
            return None
        
        logger.info(f"开始处理文件上传: {file_path}")
        
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
        def percentage(consumed_bytes, total_bytes):
            if total_bytes:
                rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
                if rate % 20 == 0:  # 每20%记录一次日志
                    logger.info(f'{file_name} 上传进度: {rate}%')
        
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
        retry_interval = 10  # 轮询间隔（秒）
        
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

【主要文字稿】: 这是从语音转写服务（如"通义听悟"）导出的、包含精确时间戳（毫秒级）和说话人信息的结构化文本。这是所有分析的主要事实来源（Primary Source of Truth）。

**重要说明：发言人识别规则**
- 发言人1：这是我的真实语音记录，包含所有有价值的工作内容、决策、想法和行动计划。
- 发言人2：这通常是环境音、噪音或无关内容，不具备参考价值，应被忽略。
- 在分析时，请专注于发言人1的内容，发言人2的内容可以完全忽略。

# 核心任务指令 (Core Task Directives)
请严格按照以下步骤执行任务：

1. 深度分析与提炼 (In-depth Analysis & Synthesis):
- 主要分析: 彻底解析文字稿中发言人1的内容，提取每一个对话片段、起止时间和核心内容。完全忽略发言人2的内容。
- 识别主题: 识别出全天讨论的各个核心议题（例如：A项目思考、B产品战略规划、与C客户的沟通准备等）。
- 挖掘关键信息: 在每个议题下，精准定位关键决策、数据点、思考过程、结论，以及我给自己分配的行动计划（Action Items）。

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