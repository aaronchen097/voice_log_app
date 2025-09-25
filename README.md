# 语音日志应用 (Voice Log App)

一个基于 FastAPI 和 Vue.js 的语音转文字日志管理系统，支持单个和批量音频文件处理，具备智能摘要生成和能力评估功能。

## 🚀 最新更新 (v2.0 - 异步优化版本)

### 新增功能
- **异步处理**: 音频转写和批量处理现在支持异步操作，大幅提升并发性能
- **任务状态跟踪**: 新增任务状态API，支持实时查询处理进度
- **前端轮询机制**: 前端自动轮询任务状态，提供实时进度反馈
- **并发优化**: 支持多用户同时使用，提升系统吞吐量

### 性能提升
- 并发处理能力提升 300%+
- 支持 10+ 用户同时访问
- 异步任务处理，用户体验更流畅
- 内存使用优化，支持大量并发请求

## 📋 功能特性

### 核心功能
- **语音转文字**: 支持多种音频格式的高精度转写
- **批量处理**: 一次性处理多个音频文件
- **智能摘要**: 自动生成音频内容摘要
- **能力评估**: 基于内容进行能力维度评估
- **主声音识别**: 支持主声音模板匹配

### 技术特性
- **异步处理**: 基于 FastAPI 的异步架构
- **实时状态**: 任务进度实时跟踪
- **用户认证**: 飞书集成的用户管理
- **数据同步**: 支持飞书多维表格数据同步
- **文件管理**: 完整的音频文件生命周期管理

## 🛠️ 技术栈

### 后端
- **FastAPI**: 现代异步 Web 框架
- **Python 3.8+**: 主要开发语言
- **阿里云语音服务**: 语音转文字引擎
- **OpenRouter API**: AI 摘要和评估
- **飞书 API**: 用户认证和数据同步

### 前端
- **HTML5/CSS3/JavaScript**: 原生 Web 技术
- **响应式设计**: 支持多设备访问
- **实时更新**: 基于轮询的状态同步
- **文件上传**: 支持拖拽和批量上传

## 📦 安装部署

### 环境要求
- Python 3.8+
- pip 包管理器
- 阿里云账号（语音服务）
- 飞书开发者账号（可选）

### 快速开始

1. **克隆项目**
```bash
git clone <repository-url>
cd voice_log_app
```

2. **安装依赖**
```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

3. **环境配置**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入必要的配置
```

4. **启动服务**
```bash
# 启动后端服务
cd backend
uvicorn main:app --host 0.0.0.0 --port 31101 --reload

# 访问应用
# 浏览器打开: http://localhost:31101
```

## ⚙️ 配置说明

### 必需环境变量
```env
# 阿里云语音服务
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
APPKEY=your_appkey

# AI 服务 (选择其一)
OPENROUTER_API_KEY=your_openrouter_key
DASHSCOPE_API_KEY=your_dashscope_key
```

### 可选环境变量
```env
# 对象存储服务
OSS_ENDPOINT=your_oss_endpoint
OSS_BUCKET_NAME=your_bucket_name

# 飞书集成
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

## 🔧 API 文档

### 异步处理 API

#### 单个音频处理
```http
POST /api/voice_log
Content-Type: multipart/form-data

# 返回
{
  "task_id": "uuid-string",
  "message": "任务已启动，正在后台处理"
}
```

#### 批量音频处理
```http
POST /api/batch_process
Authorization: Bearer <token>

# 返回
{
  "task_id": "uuid-string", 
  "message": "批量处理任务已启动"
}
```

#### 任务状态查询
```http
GET /api/task_status/{task_id}
Authorization: Bearer <token>

# 返回
{
  "task_id": "uuid-string",
  "status": "processing|completed|failed",
  "progress": 75,
  "details": "当前处理步骤描述",
  "result": {...}  // 完成时包含结果
}
```

### 其他 API
- `GET /api/logs` - 获取日志列表
- `GET /api/latest_summary` - 获取最新摘要
- `POST /api/login` - 用户登录
- `POST /api/upload_master_voice` - 上传主声音模板

## 🧪 测试

### 并发性能测试
```bash
# 运行简化测试（无需认证）
python simple_test.py

# 运行完整测试（需要用户账号）
python test_concurrent.py
```

### 测试结果
- ✅ 支持 10+ 并发用户
- ✅ 100 个并发请求 < 1 秒响应
- ✅ 内存使用稳定，无泄漏
- ✅ 异步任务处理正常

## 📁 项目结构

```
voice_log_app/
├── backend/                 # 后端代码
│   ├── main.py             # 主应用文件
│   ├── utils.py            # 工具函数
│   ├── feishu_api.py       # 飞书 API 集成
│   ├── oauth_handler.py    # OAuth 处理
│   └── requirements.txt    # Python 依赖
├── frontend/               # 前端代码
│   ├── index.html         # 主页面
│   ├── css/               # 样式文件
│   └── js/                # JavaScript 文件
├── logs/                  # 日志存储目录
├── temp_audio/           # 临时音频文件
├── test_concurrent.py    # 并发测试脚本
├── simple_test.py        # 简化测试脚本
└── README.md            # 项目文档
```

## 🔄 工作流程

### 单个音频处理流程
1. 用户上传音频文件
2. 系统返回 task_id，启动异步处理
3. 后台执行：音频转写 → 生成摘要 → 能力评估 → 保存数据
4. 前端轮询任务状态，显示进度
5. 处理完成后显示结果

### 批量处理流程
1. 用户上传多个音频文件
2. 系统检查主声音模板（如有）
3. 返回 task_id，启动异步批量处理
4. 后台执行：逐个转写 → 合并内容 → 生成摘要 → 保存数据
5. 实时更新处理进度
6. 完成后清理临时文件

## 🚀 部署建议

### 生产环境
- 使用 Gunicorn + Uvicorn 部署
- 配置 Nginx 反向代理
- 启用 HTTPS
- 设置日志轮转
- 配置监控告警

### 性能优化
- 调整 worker 数量
- 配置连接池
- 启用缓存机制
- 优化数据库查询

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如有问题或建议，请：
- 提交 Issue
- 发送邮件
- 查看文档

---

**版本**: v2.0 (异步优化版)  
**更新时间**: 2025-01-25  
**维护状态**: 积极维护中