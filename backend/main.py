from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Form, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from datetime import datetime
import logging
from dotenv import load_dotenv
from utils import (
    transcribe_audio,
    get_summary,
    generate_capability_assessment,
    load_and_index_logs,
    query_logs,
    get_latest_log_summary,
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
    version="1.2.0",
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
    接收一个音频文件，进行以下处理：
    1.  **语音转文字**：将音频内容转换为文本。
    2.  **生成摘要**：对识别出的文本进行智能摘要。
    3.  **保存日志**：将文本和摘要保存为 Markdown 格式的日志文件。
    4.  **保存到飞书**：将日志保存到飞书多维表格。
    5.  **更新索引**：将新生成的日志文件加入到检索引擎中。
    """
    try:
        # 读取上传的音频文件
        contents = await file.read()
        
        # 保存临时文件
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        temp_filepath = os.path.join(temp_dir, temp_filename)
        
        with open(temp_filepath, "wb") as temp_file:
            temp_file.write(contents)

        logging.info(f"用户 {current_user.username} 开始处理音频文件: {temp_filename}")

        # 1. 语音转文字
        text = transcribe_audio(temp_filepath)
        
        # 清理临时文件
        try:
            os.remove(temp_filepath)
        except:
            pass
            
        if not text:
            raise HTTPException(status_code=400, detail="无法识别音频内容")

        # 2. 生成摘要
        summary = get_summary(text)
        
        # 3. 生成个人能力评估
        capability_assessment = generate_capability_assessment(text, f"用户: {current_user.username}")

        # 4. 保存到飞书多维表格
        feishu_save_success = save_voice_log(
            content=summary,  # 日志内容字段存储AI智能摘要
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
            f.write(f"**文件名:** {file.filename}\n\n")
            f.write(f"## 识别内容\n\n")
            f.write(f"{text}\n")

        # 6. 更新全局索引
        global index, documents
        new_index, new_documents = load_and_index_logs()
        index = new_index
        documents = new_documents

        logging.info(f"用户 {current_user.username} 音频文件处理完成: {file.filename}")

        return JSONResponse(
            content={
                "success": True,
                "text": text, 
                "summary": summary,
                "capability_assessment": capability_assessment,
                "filename": log_filename,
                "saved_to_feishu": feishu_save_success
            }
        )
    except Exception as e:
        logging.error(f"用户 {current_user.username if 'current_user' in locals() else 'unknown'} 上传过程发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

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
    统一处理用户的所有音频片段：按顺序转写后拼接，然后进行AI总结
    """
    try:
        segments = getattr(current_user, 'batch_audio_segments', [])
        if not segments:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "没有待处理的音频片段"
                }
            )
        
        logging.info(f"用户 {current_user.username} 开始批量处理 {len(segments)} 个音频片段")
        
        # 按上传时间排序
        segments.sort(key=lambda x: x["upload_time"])
        
        # 逐个转写音频片段
        all_transcriptions = []
        processed_files = []
        
        for i, segment in enumerate(segments):
            try:
                logging.info(f"正在转写第 {i+1}/{len(segments)} 个片段: {segment['filename']}")
                text = transcribe_audio(segment["filepath"])
                if text and text.strip():
                    all_transcriptions.append({
                        "filename": segment["filename"],
                        "text": text.strip(),
                        "segment_id": segment["segment_id"]
                    })
                processed_files.append(segment["filepath"])
            except Exception as e:
                logging.error(f"转写片段 {segment['filename']} 失败: {str(e)}")
                # 继续处理其他片段
                continue
        
        if not all_transcriptions:
            raise Exception("所有音频片段转写失败")
        
        # 拼接所有转写结果
        combined_text = "\n\n".join([f"【{trans['filename']}】\n{trans['text']}" for trans in all_transcriptions])
        
        # 生成基于完整文字稿的AI摘要（使用日报模式，适合批量音频内容）
        summary = get_summary(combined_text, "day_report")
        
        # 生成个人能力评估
        capability_assessment = generate_capability_assessment(combined_text, f"用户: {current_user.username}")
        
        # 保存到飞书多维表格
        feishu_save_success = save_voice_log(
            content=summary,  # 日志内容字段存储AI智能摘要
            user_id=current_user.user_id,
            transcription=combined_text,
            summary=summary,
            capability_assessment=capability_assessment
        )
        
        # 保存本地日志
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"batch_log_{timestamp}.md"
        log_filepath = os.path.join(LOG_DIR, log_filename)
        with open(log_filepath, "w", encoding="utf-8") as f:
            f.write(f"# {summary}\n\n")
            f.write(f"**用户:** {current_user.username}\n\n")
            f.write(f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**音频片段数量:** {len(all_transcriptions)}\n\n")
            f.write(f"**文件列表:** {', '.join([trans['filename'] for trans in all_transcriptions])}\n\n")
            f.write(f"## 完整转写内容\n\n")
            f.write(f"{combined_text}\n")
        
        # 清理临时文件
        for filepath in processed_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logging.warning(f"清理临时文件失败 {filepath}: {str(e)}")
        
        # 清空用户的批量音频片段列表
        current_user.batch_audio_segments = []
        
        # 更新全局索引
        global index, documents
        new_index, new_documents = load_and_index_logs()
        index = new_index
        documents = new_documents
        
        logging.info(f"用户 {current_user.username} 批量处理完成，共处理 {len(all_transcriptions)} 个音频片段")
        
        return JSONResponse(
            content={
                "success": True,
                "processed_count": len(all_transcriptions),
                "combined_text": combined_text,
                "summary": summary,
                "capability_assessment": capability_assessment,
                "filename": log_filename,
                "saved_to_feishu": feishu_save_success
            }
        )
    except Exception as e:
        logging.error(f"用户 {current_user.username if 'current_user' in locals() else 'unknown'} 批量处理过程发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

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

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.mount("/frontend", StaticFiles(directory="../frontend"), name="frontend")

# 将根路径指向 index.html
@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse('../frontend/index.html')

@app.get("/login", include_in_schema=False)
async def login_page():
    """返回登录页面"""
    return FileResponse('../frontend/login.html')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)