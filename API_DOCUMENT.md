# API 接口文档

## 概述

语音智能日志系统提供了一套完整的RESTful API接口，支持音频上传、语音转录、AI摘要生成、飞书OAuth认证和多维表格集成等功能。

## 基础信息

- **Base URL**: `http://localhost:8000` (本地开发)
- **Content-Type**: `application/json` (除文件上传接口外)
- **认证方式**: 飞书OAuth 2.0

## 音频处理接口

### 1. 上传音频文件（单文件模式）

**接口**: `POST /upload_audio`

**描述**: 上传音频文件进行语音转录和AI摘要生成

**请求参数**:
- `file` (FormData): 音频文件，支持格式：wav, mp3, m4a, flac, aac, ogg
- `user_id` (FormData, 可选): 用户ID，用于飞书多维表格关联

**响应示例**:
```json
{
  "task_id": "uuid-string",
  "message": "音频上传成功，开始处理",
  "filename": "audio.wav"
}
```

### 2. 批量上传音频片段

**接口**: `POST /api/batch_upload`

**描述**: 批量上传多个音频片段，用于分段音频统一转写功能

**请求参数**:
- `file` (FormData): 音频文件，支持格式：wav, mp3, m4a, flac, aac, ogg
- `user_id` (FormData, 可选): 用户ID，用于飞书多维表格关联

**响应示例**:
```json
{
  "success": true,
  "message": "音频片段上传成功",
  "filename": "segment_001.wav",
  "segment_id": "uuid-string"
}
```

### 3. 统一转写批量音频

**接口**: `POST /api/batch_transcribe`

**描述**: 对所有已上传的音频片段进行统一转写和AI摘要生成

**请求体**:
```json
{
  "user_id": "ou_xxxxxxxxxxxxxxxxx"
}
```

**响应示例**:
```json
{
  "task_id": "uuid-string",
  "message": "开始统一转写处理",
  "segments_count": 5
}
```

### 2. 获取任务状态

**接口**: `GET /task_status/{task_id}`

**描述**: 查询音频处理任务的状态和结果

**路径参数**:
- `task_id`: 任务ID

**响应示例**:
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "transcription": "转录文本内容...",
  "summary": "AI生成的摘要内容...",
  "capability_assessment": "个人能力评估内容...",
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:05:00Z"
}
```

**状态值说明**:
- `pending`: 任务排队中
- `processing`: 正在处理
- `completed`: 处理完成
- `failed`: 处理失败

## 飞书OAuth认证接口

### 1. 发起OAuth登录

**接口**: `GET /auth/login`

**描述**: 重定向到飞书OAuth授权页面

**响应**: 302重定向到飞书授权URL

### 2. OAuth回调处理

**接口**: `GET /auth/callback`

**描述**: 处理飞书OAuth回调，获取用户信息

**查询参数**:
- `code`: 飞书返回的授权码
- `state`: 状态参数（可选）

**响应**: 302重定向到主页面，并设置认证Cookie

### 3. 检查认证状态

**接口**: `GET /auth/status`

**描述**: 检查当前用户的认证状态

**响应示例**:
```json
{
  "authenticated": true,
  "user_info": {
    "user_id": "ou_xxxxxxxxxxxxxxxxx",
    "name": "用户姓名",
    "avatar_url": "头像URL"
  }
}
```

## 飞书多维表格接口

### 1. 保存语音日志

**接口**: `POST /save_voice_log`

**描述**: 将语音转录和AI摘要结果保存到飞书多维表格

**请求体**:
```json
{
  "user_id": "ou_xxxxxxxxxxxxxxxxx",
  "transcription": "语音转录内容",
  "summary": "AI摘要内容",
  "capability_assessment": "个人能力评估",
  "audio_duration": 120,
  "filename": "audio.wav"
}
```

**响应示例**:
```json
{
  "success": true,
  "record_id": "recxxxxxxxxxxxxxx",
  "message": "语音日志保存成功"
}
```

### 2. 获取表格字段信息（调试用）

**接口**: `GET /feishu/fields`

**描述**: 获取飞书多维表格的字段信息，用于调试和字段映射

**响应示例**:
```json
{
  "fields": [
    {
      "field_id": "fldxxxxxxxxxxxxxx",
      "field_name": "人员",
      "type": 11,
      "description": "人员字段"
    },
    {
      "field_id": "fldxxxxxxxxxxxxxx",
      "field_name": "语音转录结果",
      "type": 1,
      "description": "文本字段"
    }
  ]
}
```

## 静态文件接口

### 1. 主页面

**接口**: `GET /`

**描述**: 返回应用主页面

**响应**: HTML页面

### 2. 静态资源

**接口**: `GET /static/{file_path}`

**描述**: 获取静态资源文件（CSS、JS、图片等）

## 错误处理

### 错误响应格式

```json
{
  "error": "错误类型",
  "message": "详细错误信息",
  "code": "错误代码"
}
```

### 常见错误码

- `400`: 请求参数错误
- `401`: 未认证或认证失败
- `403`: 权限不足
- `404`: 资源不存在
- `413`: 文件过大
- `415`: 不支持的文件格式
- `500`: 服务器内部错误

## 人员字段格式说明

系统支持多种人员字段格式，会自动转换为飞书API要求的格式：

### 1. 字符串格式（推荐）
```json
"人员": "ou_xxxxxxxxxxxxxxxxx"
```

### 2. 对象数组格式
```json
"人员": [
  {
    "id": "ou_xxxxxxxxxxxxxxxxx",
    "type": "user_id"
  }
]
```

### 3. 字符串数组格式
```json
"人员": ["ou_xxxxxxxxxxxxxxxxx"]
```

## 使用示例

### JavaScript示例

```javascript
// 上传音频文件
const formData = new FormData();
formData.append('file', audioFile);
formData.append('user_id', 'ou_xxxxxxxxxxxxxxxxx');

fetch('/upload_audio', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('任务ID:', data.task_id);
  // 轮询任务状态
  checkTaskStatus(data.task_id);
});

// 检查任务状态
function checkTaskStatus(taskId) {
  fetch(`/task_status/${taskId}`)
  .then(response => response.json())
  .then(data => {
    if (data.status === 'completed') {
      console.log('转录结果:', data.transcription);
      console.log('AI摘要:', data.summary);
    } else if (data.status === 'processing') {
      // 继续轮询
      setTimeout(() => checkTaskStatus(taskId), 2000);
    }
  });
}
```

### Python示例

```python
import requests

# 上传音频文件
with open('audio.wav', 'rb') as f:
    files = {'file': f}
    data = {'user_id': 'ou_xxxxxxxxxxxxxxxxx'}
    response = requests.post('http://localhost:8000/upload_audio', 
                           files=files, data=data)
    result = response.json()
    task_id = result['task_id']

# 检查任务状态
response = requests.get(f'http://localhost:8000/task_status/{task_id}')
result = response.json()
print(f"状态: {result['status']}")
if result['status'] == 'completed':
    print(f"转录结果: {result['transcription']}")
    print(f"AI摘要: {result['summary']}")
```

## 更新日志

### v1.3.0 (2024-01-20)
- 🆕 新增分段音频统一转写功能
- 🆕 新增批量上传接口 `POST /api/batch_upload`
- 🆕 新增统一转写接口 `POST /api/batch_transcribe`
- 🔄 前端支持双模式切换（单文件模式/批量模式）
- 🎨 优化用户界面，新增批量模式UI组件
- 🐛 修复前端提示函数未定义的问题

### v1.2.0 (2024-01-15)
- 新增飞书多维表格集成功能
- 优化人员字段格式处理，支持多种格式自动转换
- 新增个人能力评估功能
- 完善错误处理机制

### v1.1.0 (2024-01-10)
- 新增飞书OAuth认证功能
- 优化音频处理流程
- 新增任务状态查询接口

### v1.0.0 (2024-01-01)
- 初始版本发布
- 基础音频上传和转录功能
- AI摘要生成功能