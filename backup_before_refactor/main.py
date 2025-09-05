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

class LoginRequest(BaseModel):
    username: str
    password: str

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

        # 3. 保存到飞书多维表格
        feishu_save_success = save_voice_log(
            content=summary,  # 日志内容字段存储AI智能摘要
            user_id=current_user.user_id,
            transcription=text,
            summary=summary
        )

        # 4. 保存本地日志
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

        # 5. 更新全局索引
        global index, documents
        new_index, new_documents = load_and_index_logs()
        index = new_index
        documents = new_documents

        logging.info(f"用户 {current_user.username} 音频文件处理完成: {file.filename}")

        return JSONResponse(
            content={
                "text": text, 
                "summary": summary, 
                "filename": log_filename,
                "saved_to_feishu": feishu_save_success
            }
        )
    except Exception as e:
        logging.error(f"用户 {current_user.username if 'current_user' in locals() else 'unknown'} 上传过程发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


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
async def get_user_info(session_id: str = Query(...)):
    """获取当前登录用户信息"""
    try:
        if session_id in user_sessions:
            user_session = user_sessions[session_id]
            return JSONResponse({
                "success": True,
                "user": {
                    "username": user_session.username,
                    "user_id": user_session.user_id,
                    "login_time": user_session.login_time
                }
            })
        else:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "用户未登录或会话已过期"
                }
            )
    except Exception as e:
        logging.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败: {str(e)}")



# 定义摘要请求模型
class SummaryRequest(BaseModel):
    text: str
    summary_type: str = "day_report"
    model: str = "qwen-plus"

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

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# 将根路径指向 index.html
@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse('frontend/index.html')

@app.get("/login", include_in_schema=False)
async def login_page():
    """返回登录页面"""
    return FileResponse("frontend/login.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)