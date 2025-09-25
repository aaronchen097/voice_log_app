# API 接口文档

## 概述

语音日志应用提供了一套完整的 RESTful API，支持异步音频处理、任务状态跟踪、用户认证等功能。所有 API 都基于 FastAPI 构建，支持高并发和异步处理。

## 基础信息

- **基础URL**: `http://localhost:31101`
- **API版本**: v2.0 (异步优化版)
- **内容类型**: `application/json` (除文件上传外)
- **认证方式**: Bearer Token

## 认证

### 获取访问令牌

**端点**: `POST /api/login`

**描述**: 通过飞书OAuth获取访问令牌

**请求参数**:
```json
{
  "code": "string",  // 飞书OAuth授权码
  "state": "string"  // 状态参数
}
```

**响应**:
```json
{
  "success": true,
  "message": "登录成功",
  "user": {
    "user_id": "ou_xxxxxxxxxx",
    "name": "用户名",
    "avatar_url": "头像URL"
  }
}
```

**状态码**:
- `200`: 登录成功
- `400`: 参数错误
- `401`: 认证失败

---

## 音频处理 API

### 1. 单个音频处理 (异步)

**端点**: `POST /api/voice_log`

**描述**: 上传单个音频文件进行异步处理

**请求**:
- **Content-Type**: `multipart/form-data`
- **参数**:
  - `audio_file`: 音频文件 (必需)
  - `use_master_voice`: 是否使用主声音模板 (可选, 默认false)

**响应**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "任务已启动，正在后台处理"
}
```

**支持的音频格式**:
- WAV, MP3, M4A, FLAC, AAC, OGG
- 最大文件大小: 100MB

**状态码**:
- `200`: 任务创建成功
- `400`: 文件格式不支持或文件过大
- `500`: 服务器内部错误

### 2. 批量音频处理 (异步)

**端点**: `POST /api/batch_process`

**描述**: 处理用户上传的所有批量音频文件

**认证**: 需要Bearer Token

**响应**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "message": "批量处理任务已启动"
}
```

**状态码**:
- `200`: 批量任务创建成功
- `401`: 未认证或token无效
- `400`: 没有待处理的音频文件
- `500`: 服务器内部错误

### 3. 批量音频上传

**端点**: `POST /api/batch_upload`

**描述**: 上传多个音频文件到批量处理队列

**认证**: 需要Bearer Token

**请求**:
- **Content-Type**: `multipart/form-data`
- **参数**:
  - `files`: 多个音频文件

**响应**:
```json
{
  "message": "成功上传 3 个文件",
  "uploaded_files": [
    "audio1.wav",
    "audio2.mp3",
    "audio3.m4a"
  ],
  "total_files": 3
}
```

**状态码**:
- `200`: 上传成功
- `401`: 未认证
- `400`: 没有文件或格式不支持

---

## 任务状态 API

### 查询任务状态

**端点**: `GET /api/task_status/{task_id}`

**描述**: 查询异步任务的处理状态和进度

**认证**: 需要Bearer Token (批量任务) 或 无需认证 (单个任务)

**路径参数**:
- `task_id`: 任务ID (UUID格式)

**响应**:

**处理中**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "details": "正在进行语音转写..."
}
```

**已完成**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "details": "处理完成",
  "result": {
    "transcription": "转写文本内容...",
    "summary": "AI生成的摘要...",
    "capability_assessment": "能力评估结果...",
    "audio_duration": 120.5,
    "created_at": "2025-01-25T10:30:00Z"
  }
}
```

**失败**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": 0,
  "details": "处理失败: 音频文件损坏",
  "error": "AudioProcessingError: Invalid audio format"
}
```

**状态码**:
- `200`: 查询成功
- `404`: 任务不存在
- `401`: 认证失败 (批量任务)

---

## 数据查询 API

### 1. 获取日志列表

**端点**: `GET /api/logs`

**描述**: 获取语音日志列表

**认证**: 需要Bearer Token

**查询参数**:
- `page`: 页码 (默认1)
- `limit`: 每页数量 (默认10, 最大100)
- `search`: 搜索关键词 (可选)

**响应**:
```json
{
  "logs": [
    {
      "id": "log_001",
      "transcription": "会议内容转写...",
      "summary": "会议摘要...",
      "capability_assessment": "能力评估...",
      "audio_duration": 300.0,
      "created_at": "2025-01-25T10:00:00Z",
      "user_id": "ou_xxxxxxxxxx"
    }
  ],
  "total": 25,
  "page": 1,
  "limit": 10,
  "total_pages": 3
}
```

### 2. 获取最新摘要

**端点**: `GET /api/latest_summary`

**描述**: 获取最新的AI摘要

**认证**: 需要Bearer Token

**响应**:
```json
{
  "summary": "最新的AI摘要内容...",
  "created_at": "2025-01-25T10:30:00Z",
  "log_id": "log_001"
}
```

---

## 主声音管理 API

### 1. 上传主声音模板

**端点**: `POST /api/upload_master_voice`

**描述**: 上传主声音模板文件

**认证**: 需要Bearer Token

**请求**:
- **Content-Type**: `multipart/form-data`
- **参数**:
  - `master_voice_file`: 主声音音频文件

**响应**:
```json
{
  "message": "主声音模板上传成功",
  "filename": "master_voice_20250125.wav"
}
```

### 2. 检查主声音状态

**端点**: `GET /api/master_voice_status`

**描述**: 检查当前用户是否已上传主声音模板

**认证**: 需要Bearer Token

**响应**:
```json
{
  "has_master_voice": true,
  "filename": "master_voice_20250125.wav",
  "uploaded_at": "2025-01-25T09:00:00Z"
}
```

---

## 批量管理 API

### 1. 清空批量音频

**端点**: `DELETE /api/clear_batch_audio`

**描述**: 清空当前用户的所有批量音频文件

**认证**: 需要Bearer Token

**响应**:
```json
{
  "message": "已清空所有批量音频文件",
  "cleared_count": 5
}
```

### 2. 获取批量音频列表

**端点**: `GET /api/batch_audio_list`

**描述**: 获取当前用户的批量音频文件列表

**认证**: 需要Bearer Token

**响应**:
```json
{
  "files": [
    {
      "filename": "audio1.wav",
      "size": 1024000,
      "uploaded_at": "2025-01-25T10:00:00Z"
    },
    {
      "filename": "audio2.mp3", 
      "size": 2048000,
      "uploaded_at": "2025-01-25T10:01:00Z"
    }
  ],
  "total_count": 2,
  "total_size": 3072000
}
```

---

## 系统 API

### 1. 健康检查

**端点**: `GET /api/health`

**描述**: 检查系统健康状态

**认证**: 无需认证

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-25T10:30:00Z",
  "version": "v2.0",
  "uptime": 3600
}
```

### 2. 系统信息

**端点**: `GET /api/info`

**描述**: 获取系统基本信息

**认证**: 无需认证

**响应**:
```json
{
  "app_name": "语音日志应用",
  "version": "v2.0",
  "api_version": "2.0",
  "supported_formats": ["wav", "mp3", "m4a", "flac", "aac", "ogg"],
  "max_file_size": "100MB",
  "features": {
    "async_processing": true,
    "batch_processing": true,
    "master_voice": true,
    "ai_summary": true,
    "capability_assessment": true
  }
}
```

---

## 错误处理

### 标准错误响应格式

```json
{
  "error": "错误类型",
  "message": "详细错误信息",
  "details": "额外的错误详情",
  "timestamp": "2025-01-25T10:30:00Z"
}
```

### 常见错误码

| 状态码 | 错误类型 | 描述 |
|--------|----------|------|
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证或认证失败 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 413 | Payload Too Large | 文件过大 |
| 415 | Unsupported Media Type | 不支持的文件格式 |
| 422 | Unprocessable Entity | 请求格式正确但内容无效 |
| 429 | Too Many Requests | 请求频率过高 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务暂时不可用 |

---

## 使用示例

### JavaScript 示例

```javascript
// 1. 上传单个音频文件
async function uploadAudio(file) {
  const formData = new FormData();
  formData.append('audio_file', file);
  
  const response = await fetch('/api/voice_log', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  return result.task_id;
}

// 2. 轮询任务状态
async function pollTaskStatus(taskId) {
  const response = await fetch(`/api/task_status/${taskId}`);
  const status = await response.json();
  
  if (status.status === 'completed') {
    console.log('处理完成:', status.result);
    return status.result;
  } else if (status.status === 'failed') {
    console.error('处理失败:', status.details);
    throw new Error(status.details);
  } else {
    console.log(`处理中: ${status.progress}% - ${status.details}`);
    // 继续轮询
    setTimeout(() => pollTaskStatus(taskId), 2000);
  }
}

// 3. 批量处理
async function batchProcess(token) {
  const response = await fetch('/api/batch_process', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const result = await response.json();
  return result.task_id;
}
```

### Python 示例

```python
import requests
import time

# 1. 上传音频文件
def upload_audio(file_path):
    with open(file_path, 'rb') as f:
        files = {'audio_file': f}
        response = requests.post('http://localhost:31101/api/voice_log', files=files)
        return response.json()['task_id']

# 2. 轮询任务状态
def poll_task_status(task_id, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    while True:
        response = requests.get(f'http://localhost:31101/api/task_status/{task_id}', headers=headers)
        status = response.json()
        
        if status['status'] == 'completed':
            return status['result']
        elif status['status'] == 'failed':
            raise Exception(status['details'])
        else:
            print(f"处理中: {status['progress']}% - {status['details']}")
            time.sleep(2)

# 3. 完整流程
def process_audio(file_path):
    task_id = upload_audio(file_path)
    result = poll_task_status(task_id)
    print("转写结果:", result['transcription'])
    print("AI摘要:", result['summary'])
    return result
```

---

## 性能指标

### 并发能力
- **最大并发用户**: 10+
- **单个请求响应时间**: < 100ms
- **批量处理吞吐量**: 5-10 文件/分钟
- **任务状态查询**: < 50ms

### 文件限制
- **单文件大小**: 最大 100MB
- **批量文件数量**: 最大 20 个文件
- **支持格式**: WAV, MP3, M4A, FLAC, AAC, OGG
- **音频时长**: 建议 < 60 分钟

### 存储和缓存
- **任务状态缓存**: 24 小时
- **临时文件清理**: 处理完成后自动清理
- **日志保留**: 永久保存 (可配置)

---

## 更新日志

### v2.0 (2025-01-25)
- ✅ 新增异步处理架构
- ✅ 添加任务状态跟踪API
- ✅ 优化并发性能
- ✅ 改进错误处理机制
- ✅ 增强前端轮询功能

### v1.0 (2024-12-01)
- ✅ 基础语音转写功能
- ✅ AI摘要生成
- ✅ 飞书集成
- ✅ 批量处理支持

---

**文档版本**: v2.0  
**最后更新**: 2025-01-25  
**维护者**: 开发团队