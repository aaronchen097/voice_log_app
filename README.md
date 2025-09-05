# 语音智能日志系统

## 项目简介

**语音智能日志系统** 是一款基于FastAPI的Web应用，旨在提供高效的语音转录和智能摘要服务。它集成了阿里云的语音识别（ASR）和通义千问大型语言模型（LLM），可将您的音频文件快速转换为文字，并生成精准的摘要。

## 主要功能

- 🎵 **多种音频格式支持**: 可上传 `.wav`, `.mp3`, `.m4a`, `.flac`, `.aac`, `.ogg` 等多种格式的音频文件。
- 🔊 **高精度语音转录**: 利用阿里云语音识别服务，确保高准确率的文本转换。
- 🤖 **AI智能摘要**: 集成通义千问（qwen-plus）模型，自动生成会议纪要、内容摘要等。
- 📊 **实时任务跟踪**: 在Web界面上实时查看音频处理、转录和摘要生成的任务状态。
- 🔐 **飞书OAuth认证**: 支持飞书账号登录，提供安全的用户认证和授权机制。
- 🌐 **简洁Web界面**: 提供一个干净、直观的前端界面，方便用户上传和查看结果。
- 📚 **完整的API文档**: 通过Swagger UI和ReDoc提供交互式的API文档。

## 技术栈

- **后端**: Python 3.11, FastAPI
- **语音识别**: 阿里云实时语音识别服务
- **AI模型**: 阿里云通义千问（qwen-plus）
- **云存储**: 阿里云对象存储（OSS）
- **容器化**: Docker, Docker Compose

## 项目结构

```
├── backend/             # 后端代码目录
│   ├── __init__.py      # Python包初始化文件
│   ├── main.py          # FastAPI主应用
│   ├── utils.py         # 核心工具函数（语音识别、摘要生成）
│   └── requirements.txt # Python依赖
├── static/              # 静态资源目录
│   ├── css/
│   │   └── styles.css   # 样式表
│   └── js/
│       └── script.js    # JavaScript逻辑
├── frontend/            # 前端文件（兼容保留）
│   ├── index.html       # 前端主页
│   ├── script.js        # JavaScript逻辑
│   └── styles.css       # 样式表
├── logs/                # 日志存储目录
├── index.html           # 应用主页
├── main.py              # 主应用入口（兼容保留）
├── utils.py             # 工具函数（兼容保留）
├── requirements.txt     # Python依赖（兼容保留）
├── Dockerfile           # Docker镜像构建文件
├── docker-compose.yml   # Docker Compose编排文件
├── .env.example         # 环境变量配置文件示例
├── DEPLOYMENT_GUIDE.md  # 详细的部署指南
├── API_DOCUMENT.md      # API接口文档
├── CONTRIBUTING.md      # 贡献指南
└── README.md            # 本文档
```

## 快速开始

### 环境准备

- Python 3.11+
- Docker 和 Docker Compose
- 阿里云账户，并开通 **AccessKey**、**语音识别**、**对象存储OSS** 和 **通义千問** 服务。

### 使用Docker部署（推荐）

1.  **克隆项目**
    ```bash
    git clone <your-repository-url>
    cd 语音智能日志系统
    ```

2.  **配置环境变量**
    复制 `.env.example` 文件为 `.env`，并填入您的阿里云密钥和相关配置。
    ```bash
    cp .env.example .env
    ```

    **`.env` 文件内容:**
    ```
    # 阿里云配置
    ALIBABA_CLOUD_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
    ALIBABA_CLOUD_ACCESS_KEY_SECRET="YOUR_ACCESS_KEY_SECRET"
    APPKEY="YOUR_APPKEY"
    OSS_ENDPOINT="YOUR_OSS_ENDPOINT"
    OSS_BUCKET_NAME="YOUR_OSS_BUCKET_NAME"
    DASHSCOPE_API_KEY="YOUR_DASHSCOPE_API_KEY"
    
    # 飞书OAuth配置
    FEISHU_APP_ID="YOUR_FEISHU_APP_ID"
    FEISHU_APP_SECRET="YOUR_FEISHU_APP_SECRET"
    FEISHU_REDIRECT_URI="http://localhost:8000/auth/callback"
    
    # 服务配置
    PORT=31101
    ```

3.  **构建并启动服务**
    ```bash
    docker-compose up --build -d
    ```

### 本地开发

1.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

2.  **配置环境变量**
    同上，创建并配置 `.env` 文件。

3.  **启动服务**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 31101 --reload
    ```

## 使用说明

服务启动后，您可以访问以下地址：

- **前端界面**: `http://localhost:31101`
- **API文档 (Swagger)**: `http://localhost:31101/docs`
- **API文档 (ReDoc)**: `http://localhost:31101/redoc`

通过前端界面，您可以上传音频文件，并查看转录和摘要的结果。

## 飞书OAuth认证配置

本系统支持飞书OAuth认证，用户可以使用飞书账号登录系统。要启用此功能，需要进行以下配置：

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 在应用管理页面获取 `App ID` 和 `App Secret`
4. 配置重定向URL：`http://your-domain:port/auth/callback`

### 2. 配置环境变量

在 `.env` 文件中添加以下配置：

```bash
FEISHU_APP_ID="cli_xxxxxxxxxxxxxxxxx"     # 飞书应用的App ID
FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"      # 飞书应用的App Secret
FEISHU_REDIRECT_URI="http://localhost:8000/auth/callback"  # OAuth回调地址
```

### 3. OAuth认证流程

1. 用户点击"使用飞书账号登录"按钮
2. 系统重定向到飞书授权页面
3. 用户在飞书页面完成授权
4. 飞书回调到系统，携带授权码
5. 系统使用授权码获取用户访问令牌
6. 完成登录，跳转到主页面

### 4. API端点

- `GET /auth/login` - 发起OAuth登录
- `GET /auth/callback` - OAuth回调处理
- `GET /auth/status` - 检查认证状态

##  Frontend

The frontend of the Voice Intelligent Log System is a modern, single-page application (SPA) designed for a seamless user experience. It is built with HTML5, CSS3, and modern JavaScript (ES6+), and is responsible for all user interactions, including file uploads, status monitoring, and displaying results.

### Key Frontend Features

- **Dual Upload Modes**: Supports both local file uploads and uploads from a URL.
- **Drag and Drop**: Allows users to drag and drop audio files directly into the browser.
- **Real-time Progress**: Provides real-time feedback on upload and transcription progress.
- **AI Summary Generation**: Integrates with the backend to generate and display AI-powered summaries.
- **Transcription Viewer**: Displays the formatted transcription text with speaker and timestamp information.
- **Local History**: Stores recent transcriptions in the browser's local storage for easy access.
- **Responsive Design**: Ensures a consistent experience across different devices and screen sizes.

For more detailed information on the frontend architecture, development, and deployment, please refer to the [FRONTEND_REFACTOR_DEV_DOC.md](FRONTEND_REFACTOR_DEV_DOC.md) file.

## 部署

详细的部署说明，请参阅 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)。

### Build and Deployment Scripts

The project includes scripts to simplify the build and deployment process:

- **`local_build.sh` / `local_build.ps1`**: These scripts build the Docker image and save it as a `.tar` file. You can optionally pass a version number as an argument.
  ```bash
  # For Linux/macOS
  ./local_build.sh v1.0.0

  # For Windows (PowerShell)
  .\local_build.ps1 -Version v1.0.0
  ```

- **`server_deploy.sh`**: This script loads the Docker image from a `.tar` file on the server, stops the old containers, and starts the new ones.
  ```bash
  ./server_deploy.sh voice-log-app-v1.0.0.tar
  ```

## 贡献

欢迎对本项目做出贡献！如果您有任何建议或发现任何问题，请随时提交 Pull Request 或 Issue。

## 许可证

本项目采用 [MIT许可证](LICENSE)。