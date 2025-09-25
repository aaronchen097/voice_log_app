from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Form, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from datetime import datetime
import logging
import uuid
import asyncio
from dotenv import load_dotenv
from utils import (
    transcribe_audio,
    get_summary,
    generate_capability_assessment,
    load_and_index_logs,
    query_logs,
    get_latest_log_summary,
    get_master_voice_path,
    prepare_audio_with_master_voice,
    cleanup_processed_audio,
    LOG_DIR
)
from feishu_api import authenticate_user, save_voice_log, get_feishu_client

# ------------------------------------------------------------
# 环境变量加载与校验
# ------------------------------------------------------------

load_dotenv()  # 自动加载同目录或上级的 .env 文件（若存在）

REQUIRED_ENV_VARS = [
    "ALIBABA_CLOUD_ACCESS_KEY_ID",
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
    "APPKEY",
]

OPTIONAL_ENV_VARS = [
    "OSS_ENDPOINT",
    "OSS_BUCKET_NAME",
    "OPENROUTER_API_KEY",
    "DASHSCOPE_API_KEY",
]

def _validate_env():
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        logging.warning(
            "缺少必要环境变量: %s (部分功能将不可用, 请在 .env 中添加)", ",".join(missing)
        )
    # 仅提示可选
    optional_missing = [k for k in OPTIONAL_ENV_VARS if not os.getenv(k)]
    if optional_missing:
        logging.info("未配置可选环境变量: %s", ",".join(optional_missing))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
_validate_env()

app = FastAPI(
    title="语音智能日志 API",
    description="一个集成了语音识别、智能摘要和日志查询功能的智能日志系统",
    version="3.0.0",
)

# 允许所有来源的跨域请求（在生产环境中应配置得更严格）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 加载并索引现有的日志文件
index, documents = load_and_index_logs()

# 全局任务存储
task_storage = {}

# 任务状态枚举
class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 任务信息模型
class TaskInfo(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

# 用户会话模型
class UserSession(BaseModel):
    username: str
    user_id: str
    login_time: str
    batch_audio_segments: list = []  # 批量音频片段列表

# 音频片段模型
class AudioSegment(BaseModel):
    segment_id: str
    filename: str
    filepath: str
    upload_time: str
    file_size: int

class LoginRequest(BaseModel):
    username: str
    password: str

# 批量处理请求模型
class BatchProcessRequest(BaseModel):
    mode: str = "batch"  # batch 或 single

# 用户会话存储（生产环境应使用Redis等）
user_sessions: Dict[str, UserSession] = {}

# 获取当前用户的依赖函数
def get_current_user(authorization: str = Header(None)):
    """
    从请求头中获取用户认证信息
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    
    try:
        # 解析Bearer token
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="无效的认证方案")
        
        # 检查会话是否存在
        if token not in user_sessions:
            raise HTTPException(status_code=401, detail="会话已过期或无效")
        
        session = user_sessions[token]
        
        # 检查会话是否过期（24小时）
        from datetime import timedelta
        if datetime.now() - datetime.fromisoformat(session.login_time) > timedelta(hours=24):
            del user_sessions[token]
            raise HTTPException(status_code=401, detail="会话已过期")
        
        return session
        
    except ValueError:
        raise HTTPException(status_code=401, detail="无效的认证格式")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"认证失败: {str(e)}")

@app.post("/api/voice_log", summary="上传语音文件并生成日志")
async def create_voice_log(file: UploadFile = File(...), current_user: UserSession = Depends(get_current_user)):
    """
    接收一个音频文件，进行异步处理：
    1. 立即返回任务ID
    2. 后台异步处理语音转文字、生成摘要等
    3. 客户端可通过任务ID查询处理状态
    """
    try:
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 读取上传的音频文件
        contents = await file.read()
        
        # 初始化任务状态
        task_storage[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "任务已创建，等待处理",
            "result": None,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 启动后台异步任务
        asyncio.create_task(process_voice_log_async(contents, file.filename, current_user, task_id))
        
        return JSONResponse(content={
            "success": True,
            "message": "音频文件上传成功，正在后台处理",
            "task_id": task_id
        })
        
    except Exception as e:
        logging.error(f"用户 {current_user.username} 上传音频文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
@app.post("/api/batch_upload", summary="批量模式：上传音频片段")
async def batch_upload_audio(file: UploadFile = File(...), current_user: UserSession = Depends(get_current_user)):
    """
    批量模式下上传音频片段，暂存不立即转写
    """
    try:
        # 读取上传的音频文件
        contents = await file.read()
        
        # 创建用户专用的批量上传目录
        batch_dir = f"batch_uploads/{current_user.user_id}"
        os.makedirs(batch_dir, exist_ok=True)
        
        # 生成唯一的片段ID和文件名
        import uuid
        segment_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{segment_id}_{timestamp}_{file.filename}"
        filepath = os.path.join(batch_dir, safe_filename)
        
        # 保存音频文件
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # 创建音频片段记录
        audio_segment = {
            "segment_id": segment_id,
            "filename": file.filename,
            "filepath": filepath,
            "upload_time": datetime.now().isoformat(),
            "file_size": len(contents)
        }
        
        # 添加到用户会话的批量音频片段列表
        if not hasattr(current_user, 'batch_audio_segments'):
            current_user.batch_audio_segments = []
        current_user.batch_audio_segments.append(audio_segment)
        
        logging.info(f"用户 {current_user.username} 上传音频片段: {file.filename}, 片段ID: {segment_id}")
        
        return JSONResponse(
            content={
                "success": True,
                "segment_id": segment_id,
                "filename": file.filename,
                "file_size": len(contents),
                "total_segments": len(current_user.batch_audio_segments)
            }
        )
    except Exception as e:
        logging.error(f"用户 {current_user.username if 'current_user' in locals() else 'unknown'} 批量上传过程发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.get("/api/batch_list", summary="获取当前用户的音频片段列表")
async def get_batch_audio_list(current_user: UserSession = Depends(get_current_user)):
    """
    获取当前用户的批量音频片段列表
    """
    try:
        segments = getattr(current_user, 'batch_audio_segments', [])
        # 返回片段信息，不包含文件路径（安全考虑）
        segment_list = []
        for segment in segments:
            segment_list.append({
                "segment_id": segment["segment_id"],
                "filename": segment["filename"],
                "upload_time": segment["upload_time"],
                "file_size": segment["file_size"]
            })
        
        return JSONResponse(
            content={
                "success": True,
                "segments": segment_list,
                "total_count": len(segment_list)
            }
        )
    except Exception as e:
        logging.error(f"获取用户 {current_user.username} 音频片段列表失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.post("/api/batch_process", summary="批量模式：统一转写所有音频片段")
async def batch_process_audio(current_user: UserSession = Depends(get_current_user)):
    """
    启动批量音频处理的异步任务
    """
    try:
        segments = current_user.batch_audio_segments
        if not segments:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "没有待处理的音频片段"
                }
            )
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        task_storage[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "批量处理任务已创建，等待处理",
            "result": None,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 启动后台异步任务
        asyncio.create_task(process_batch_audio_async(current_user, task_id))
        
        logging.info(f"用户 {current_user.username} 开始批量处理 {len(segments)} 个音频片段，任务ID: {task_id}")
        
        return JSONResponse(content={
            "success": True,
            "message": f"批量处理任务已启动，共 {len(segments)} 个音频片段",
            "task_id": task_id,
            "segments_count": len(segments)
        })
        
    except Exception as e:
        logging.error(f"用户 {current_user.username} 启动批量处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动批量处理失败: {str(e)}")
@app.delete("/api/batch_clear", summary="清空当前批次的音频片段")
async def clear_batch_audio(current_user: UserSession = Depends(get_current_user)):
    """
    清空当前用户的批量音频片段
    """
    try:
        segments = getattr(current_user, 'batch_audio_segments', [])
        
        # 删除临时文件
        deleted_count = 0
        for segment in segments:
            try:
                if os.path.exists(segment["filepath"]):
                    os.remove(segment["filepath"])
                    deleted_count += 1
            except Exception as e:
                logging.warning(f"删除临时文件失败 {segment['filepath']}: {str(e)}")
        
        # 清空片段列表
        current_user.batch_audio_segments = []
        
        logging.info(f"用户 {current_user.username} 清空批量音频片段，删除 {deleted_count} 个临时文件")
        
        return JSONResponse(
            content={
                "success": True,
                "cleared_count": len(segments),
                "deleted_files": deleted_count
            }
        )
    except Exception as e:
        logging.error(f"清空用户 {current_user.username} 音频片段失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.get("/api/query", summary="根据问题查询相关日志")
async def query_voice_logs(query: str = Query(..., description="输入你想要查询的问题")):
    """
    接收一个查询问题，在所有日志中检索最相关的条目并返回答案。
    """
    if not index:
        raise HTTPException(status_code=404, detail="没有可查询的日志文件")
    
    answer = query_logs(query, index, documents)
    return {"query": query, "answer": answer}

@app.get("/api/latest_summary", summary="获取最新的日志摘要")
async def get_latest_summary_endpoint():
    """
    获取最新一条日志的摘要信息。
    """
    summary_info = get_latest_log_summary()
    if not summary_info:
        raise HTTPException(status_code=404, detail="没有找到任何日志")
    return summary_info

@app.post("/api/login", summary="用户登录")
async def login(request: LoginRequest):
    """用户登录"""
    try:
        # 调用飞书API进行用户认证
        user_info = authenticate_user(request.username, request.password)
        
        if user_info:
            # 生成会话ID
            session_id = f"session_{int(datetime.now().timestamp())}"
            
            # 存储用户会话
            user_sessions[session_id] = UserSession(
                username=user_info['username'],
                user_id=user_info['user_id'],
                login_time=datetime.now().isoformat()
            )
            
            logging.info(f"用户 {request.username} 登录成功")
            return JSONResponse({
                "success": True,
                "message": "登录成功",
                "user": {
                    "username": user_info['username'],
                    "user_id": user_info['user_id'],
                    "session_id": session_id
                }
            })
        else:
            logging.warning(f"用户 {request.username} 登录失败：账号或密码错误")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "账号或密码错误"
                }
            )
            
    except Exception as e:
        logging.error(f"登录过程中发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")

@app.post("/api/logout", summary="用户登出")
async def logout(session_id: str = Form(...)):
    """用户登出"""
    try:
        if session_id in user_sessions:
            username = user_sessions[session_id].username
            del user_sessions[session_id]
            logging.info(f"用户 {username} 已登出")
            return JSONResponse({
                "success": True,
                "message": "登出成功"
            })
        else:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的会话"
                }
            )
    except Exception as e:
        logging.error(f"登出过程中发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登出失败: {str(e)}")



@app.get("/api/user/info", summary="获取用户信息")
async def get_user_info(current_user: UserSession = Depends(get_current_user)):
    """获取当前登录用户信息"""
    try:
        return JSONResponse({
            "success": True,
            "user": {
                "username": current_user.username,
                "user_id": current_user.user_id,
                "login_time": current_user.login_time
            }
        })
    except Exception as e:
        logging.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败: {str(e)}")



# 定义摘要请求模型
class SummaryRequest(BaseModel):
    text: str
    summary_type: str = "day_report"
    model: str = "qwen-plus"

class CapabilityAssessmentRequest(BaseModel):
    text: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/summary", summary="生成AI摘要")
async def generate_summary_endpoint(request: SummaryRequest):
    """
    根据提供的文本生成AI摘要
    """
    try:
        # 使用utils.py中的get_summary函数，但传递summary_type参数
        summary = get_summary(request.text, request.summary_type)
        return JSONResponse(content={"summary": summary})
    except Exception as e:
        print(f"摘要生成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/capability_assessment", summary="生成个人能力评估")
async def generate_capability_assessment_endpoint(request: CapabilityAssessmentRequest):
    try:
        if not request.text or request.text.strip() == "":
            raise HTTPException(status_code=400, detail="文本内容不能为空")
        
        capability_assessment = generate_capability_assessment(request.text)
        return JSONResponse(content={
            "success": True,
            "capability_assessment": capability_assessment
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"个人能力评估生成失败: {e}")
        raise HTTPException(status_code=500, detail="个人能力评估生成失败")

# 主人声音频管理接口
@app.post("/api/upload_master_voice", summary="上传主人声音频样本")
async def upload_master_voice(file: UploadFile = File(...), current_user: UserSession = Depends(get_current_user)):
    """
    上传主人声音频样本，用于后续批量转写时的发言人识别
    """
    try:
        # 检查文件类型
        if not file.filename.lower().endswith(('.wav', '.mp3', '.m4a', '.flac')):
            raise HTTPException(status_code=400, detail="不支持的音频格式，请上传 WAV、MP3、M4A 或 FLAC 格式")
        
        # 创建主人声音频存储目录
        master_voice_dir = "master_voices"
        os.makedirs(master_voice_dir, exist_ok=True)
        
        # 使用用户ID作为文件名
        file_extension = os.path.splitext(file.filename)[1]
        master_voice_filename = f"{current_user.user_id}{file_extension}"
        master_voice_path = os.path.join(master_voice_dir, master_voice_filename)
        
        # 保存主人声音频文件
        contents = await file.read()
        with open(master_voice_path, "wb") as f:
            f.write(contents)
        
        logging.info(f"用户 {current_user.username} 上传主人声音频: {master_voice_filename}")
        
        return JSONResponse(content={
            "success": True,
            "message": "主人声音频上传成功",
            "filename": master_voice_filename,
            "file_size": len(contents)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"主人声音频上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"主人声音频上传失败: {str(e)}")

@app.get("/api/check_master_voice", summary="检查用户是否已上传主人声音频")
async def check_master_voice(current_user: UserSession = Depends(get_current_user)):
    """
    检查当前用户是否已上传主人声音频样本
    """
    try:
        master_voice_dir = "master_voices"
        
        # 检查可能的音频格式
        audio_extensions = ['.wav', '.mp3', '.m4a', '.flac']
        master_voice_exists = False
        master_voice_file = None
        
        for ext in audio_extensions:
            potential_file = os.path.join(master_voice_dir, f"{current_user.user_id}{ext}")
            if os.path.exists(potential_file):
                master_voice_exists = True
                master_voice_file = f"{current_user.user_id}{ext}"
                break
        
        return JSONResponse(content={
            "success": True,
            "has_master_voice": master_voice_exists,
            "master_voice_file": master_voice_file,
            "is_first_time": not master_voice_exists
        })
        
    except Exception as e:
        logging.error(f"检查主人声音频失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查主人声音频失败: {str(e)}")

@app.delete("/api/delete_master_voice", summary="删除主人声音频样本")
async def delete_master_voice(current_user: UserSession = Depends(get_current_user)):
    """
    删除当前用户的主人声音频样本
    """
    try:
        master_voice_dir = "master_voices"
        audio_extensions = ['.wav', '.mp3', '.m4a', '.flac']
        deleted_files = []
        
        for ext in audio_extensions:
            file_path = os.path.join(master_voice_dir, f"{current_user.user_id}{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(f"{current_user.user_id}{ext}")
        
        if deleted_files:
            logging.info(f"用户 {current_user.username} 删除主人声音频: {deleted_files}")
            return JSONResponse(content={
                "success": True,
                "message": "主人声音频删除成功",
                "deleted_files": deleted_files
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "未找到主人声音频文件"
            })
        
    except Exception as e:
        logging.error(f"删除主人声音频失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除主人声音频失败: {str(e)}")

@app.get("/api/task_status/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str, current_user: UserSession = Depends(get_current_user)):
    """
    查询指定任务的状态和进度
    """
    try:
        if task_id not in task_storage:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        task_info = task_storage[task_id]
        return JSONResponse(content={
            "success": True,
            "task_id": task_id,
            "status": task_info["status"],
            "progress": task_info["progress"],
            "message": task_info["message"],
            "result": task_info["result"],
            "created_at": task_info["created_at"],
            "updated_at": task_info["updated_at"]
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")

def update_task_status(task_id: str, status: str, progress: int = 0, message: str = "", result: Optional[Dict[str, Any]] = None):
    """
    更新任务状态
    """
    if task_id in task_storage:
        task_storage[task_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            "result": result,
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

async def process_batch_audio_async(current_user: UserSession, task_id: str):
    """
    异步处理批量音频的后台任务
    """
    try:
        update_task_status(task_id, TaskStatus.PROCESSING, 5, "开始批量处理音频")
        
        # 获取用户的音频片段
        segments = current_user.batch_audio_segments
        
        if not segments:
            update_task_status(task_id, TaskStatus.FAILED, 0, "没有找到待处理的音频片段")
            return
        
        update_task_status(task_id, TaskStatus.PROCESSING, 10, f"找到 {len(segments)} 个音频片段，检查主人声")
        
        # 检查是否有主人声音频
        has_master_voice = get_master_voice_path(current_user.user_id) is not None
        
        if has_master_voice:
            processing_mode = "主人声增强模式"
        else:
            processing_mode = "标准转写模式"
        
        update_task_status(task_id, TaskStatus.PROCESSING, 15, f"使用{processing_mode}，开始逐个转写")
        
        # 按上传时间排序
        segments.sort(key=lambda x: x["upload_time"])
        
        # 逐个转写音频片段（包含主人声预处理）
        all_transcriptions = []
        processed_files = []
        
        for i, segment in enumerate(segments):
            try:
                progress = 15 + (i / len(segments)) * 60  # 15-75%的进度用于转写
                update_task_status(task_id, TaskStatus.PROCESSING, int(progress), 
                                 f"正在处理第 {i+1}/{len(segments)} 个片段: {segment['filename']}")
                
                logging.info(f"正在处理第 {i+1}/{len(segments)} 个片段: {segment['filename']}")
                
                # 根据之前检查的主人声状态进行处理
                if has_master_voice:
                    logging.info(f"为片段 {segment['filename']} 添加主人声前缀")
                    # 预处理音频：在原音频前添加主人声
                    preprocessed_path = prepare_audio_with_master_voice(
                        segment["filepath"], 
                        current_user.user_id
                    )
                    # 使用预处理后的音频进行转写
                    text = await transcribe_audio(preprocessed_path)
                    # 清理预处理的临时文件
                    cleanup_processed_audio(preprocessed_path)
                    processed_files.append(preprocessed_path)
                else:
                    logging.info(f"未找到主人声音频，直接转写片段: {segment['filename']}")
                    # 直接转写原音频
                    text = await transcribe_audio(segment["filepath"])
                
                if text and text.strip():
                    all_transcriptions.append({
                        "filename": segment["filename"],
                        "text": text.strip(),
                        "segment_id": segment["segment_id"]
                    })
                processed_files.append(segment["filepath"])
            except Exception as e:
                logging.error(f"处理片段 {segment['filename']} 失败: {str(e)}")
                # 继续处理其他片段
                continue
        
        if not all_transcriptions:
            update_task_status(task_id, TaskStatus.FAILED, 0, "所有音频片段转写失败")
            return
        
        update_task_status(task_id, TaskStatus.PROCESSING, 80, "转写完成，生成摘要")
        
        # 拼接所有转写结果
        combined_text = "\n\n".join([f"【{trans['filename']}】\n{trans['text']}" for trans in all_transcriptions])
        
        # 生成基于完整文字稿的AI摘要（使用日报模式，适合批量音频内容）
        summary = get_summary(combined_text, "day_report")
        
        update_task_status(task_id, TaskStatus.PROCESSING, 90, "生成能力评估")
        
        # 生成个人能力评估
        capability_assessment = generate_capability_assessment(combined_text, f"用户: {current_user.username}")
        
        update_task_status(task_id, TaskStatus.PROCESSING, 95, "保存到飞书和本地")
        
        # 保存到飞书多维表格
        feishu_save_success = save_voice_log(
            content=summary,  # 日志内容字段存储AI智能摘要
            user_id=current_user.user_id,
            transcription=combined_text,
            summary=summary,
            capability_assessment=capability_assessment
        )

        # 保存本地日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"batch_log_{timestamp}.md"
        log_filepath = os.path.join(LOG_DIR, log_filename)
        
        with open(log_filepath, "w", encoding="utf-8") as f:
            f.write(f"# {summary}\n\n")
            f.write(f"**用户:** {current_user.username}\n\n")
            f.write(f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**处理模式:** {processing_mode}\n\n")
            f.write(f"**音频片段数量:** {len(all_transcriptions)}\n\n")
            f.write(f"## 完整转写内容\n\n")
            f.write(f"{combined_text}\n\n")
            f.write(f"## AI智能摘要\n\n")
            f.write(f"{summary}\n\n")
            f.write(f"## 个人能力评估\n\n")
            f.write(f"{capability_assessment}\n")

        # 清理临时文件
        for filepath in processed_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logging.warning(f"清理临时文件失败 {filepath}: {e}")

        # 清空用户的批量音频片段
        current_user.batch_audio_segments.clear()

        # 更新全局索引
        global index, documents
        new_index, new_documents = load_and_index_logs()
        index = new_index
        documents = new_documents

        # 任务完成
        result = {
            "transcription": combined_text,
            "summary": summary,
            "capability_assessment": capability_assessment,
            "filename": log_filename,
            "saved_to_feishu": feishu_save_success,
            "processing_mode": processing_mode,
            "segments_count": len(all_transcriptions)
        }
        
        update_task_status(task_id, TaskStatus.COMPLETED, 100, "批量处理完成", result)
        logging.info(f"用户 {current_user.username} 批量音频处理完成: {log_filename}")

    except Exception as e:
        logging.error(f"用户 {current_user.username} 批量音频处理失败: {str(e)}")
        update_task_status(task_id, TaskStatus.FAILED, 0, f"处理失败: {str(e)}")

async def process_voice_log_async(file_content: bytes, filename: str, current_user: UserSession, task_id: str):
    """
    异步处理语音日志的后台任务
    """
    try:
        update_task_status(task_id, TaskStatus.PROCESSING, 10, "开始处理音频文件")
        
        # 保存临时文件
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        temp_filepath = os.path.join(temp_dir, temp_filename)
        
        with open(temp_filepath, "wb") as temp_file:
            temp_file.write(file_content)

        logging.info(f"用户 {current_user.username} 开始处理音频文件: {temp_filename}")
        update_task_status(task_id, TaskStatus.PROCESSING, 20, "音频文件保存完成，开始转写")

        # 1. 语音转文字
        text = await transcribe_audio(temp_filepath)
        
        # 清理临时文件
        try:
            os.remove(temp_filepath)
        except:
            pass
            
        if not text:
            update_task_status(task_id, TaskStatus.FAILED, 0, "无法识别音频内容")
            return

        update_task_status(task_id, TaskStatus.PROCESSING, 60, "转写完成，生成摘要")

        # 2. 生成摘要
        summary = get_summary(text)
        
        update_task_status(task_id, TaskStatus.PROCESSING, 80, "摘要生成完成，生成能力评估")
        
        # 3. 生成个人能力评估
        capability_assessment = generate_capability_assessment(text, f"用户: {current_user.username}")

        update_task_status(task_id, TaskStatus.PROCESSING, 90, "保存到飞书和本地")

        # 4. 保存到飞书多维表格
        feishu_save_success = save_voice_log(
            content=summary,
            user_id=current_user.user_id,
            transcription=text,
            summary=summary,
            capability_assessment=capability_assessment
        )

        # 5. 保存本地日志
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"log_{timestamp}.md"
        log_filepath = os.path.join(LOG_DIR, log_filename)
        with open(log_filepath, "w", encoding="utf-8") as f:
            f.write(f"# {summary}\n\n")
            f.write(f"**用户:** {current_user.username}\n\n")
            f.write(f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## 完整转写内容\n\n")
            f.write(f"{text}\n\n")
            f.write(f"## AI智能摘要\n\n")
            f.write(f"{summary}\n\n")
            f.write(f"## 个人能力评估\n\n")
            f.write(f"{capability_assessment}\n")

        # 6. 更新全局索引
        global index, documents
        new_index, new_documents = load_and_index_logs()
        index = new_index
        documents = new_documents

        # 任务完成
        result = {
            "transcription": text,
            "summary": summary,
            "capability_assessment": capability_assessment,
            "filename": log_filename,
            "saved_to_feishu": feishu_save_success
        }
        
        update_task_status(task_id, TaskStatus.COMPLETED, 100, "处理完成", result)
        logging.info(f"用户 {current_user.username} 语音日志处理完成: {log_filename}")

    except Exception as e:
        logging.error(f"用户 {current_user.username} 语音日志处理失败: {str(e)}")
        update_task_status(task_id, TaskStatus.FAILED, 0, f"处理失败: {str(e)}")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.mount("/frontend", StaticFiles(directory="../frontend"), name="frontend")

# 将根路径指向 index.html
@app.get("/", include_in_schema=False)
async def read_index():
    import os
    frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/index.html'))
    return FileResponse(frontend_path)

@app.get("/login", include_in_schema=False)
async def login_page():
    """返回登录页面"""
    return FileResponse('../frontend/login.html')

if __name__ == "__main__":
    import uvicorn
    # 端口通过uvicorn命令行参数控制，不在代码中硬编码
    uvicorn.run(app, host="0.0.0.0", port=31101)