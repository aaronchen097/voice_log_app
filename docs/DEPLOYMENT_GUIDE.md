# 语音智能日志系统 - 部署指南

## 📖 指南概述

本指南将帮助您成功部署“语音智能日志系统”。

### 您将学到：
-   **跨平台本地打包**：无论您使用 Windows 还是 macOS/Linux，都能轻松打包。
-   **上传关键文件**：了解哪些文件是部署所必需的。
-   **一键服务器部署**：使用优化后的脚本，平滑更新正在运行的应用。
-   **验证与访问**：如何确认应用已成功部署并对外提供服务。
-   **问题排查**：常见问题的解决方案。

### 核心理念：Docker
部署流程的核心是 Docker。我们将应用及其所有依赖打包到一个标准的“容器”（Docker 镜像）中。这个容器保证了应用在任何环境下都能以完全相同的方式运行。

---

## 🚀 第一部分：在本地打包应用程序

在这一步，我们将在您的本地开发机上，将应用程序源代码制作成一个独立的部署包。

### 步骤 1：环境准备
- **Docker Desktop**: 确保您的电脑上已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

### 步骤 2：配置环境变量
项目根目录下的 `.env` 文件是所有配置的核心。

1.  **找到 `.env` 文件**：如果不存在，可以从 `.env.example` 复制一份。
2.  **填入您的配置**：用文本编辑器打开并填入您的真实密钥和配置。

    ```env
    ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
    ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
    APPKEY=your_app_key
    OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
    OSS_BUCKET_NAME=aaronchenaudio
    PORT=31101
    ```

### 步骤 3：运行打包脚本 (跨平台)
我们提供了针对不同操作系统的打包脚本。请在项目根目录下打开终端执行相应命令。

-   **如果您使用 Windows (PowerShell):**

    ```powershell
    # 使用 PowerShell 脚本打包，并指定版本号
    ./local_build.ps1 -Version v1.0.0
    ```

-   **如果您使用 macOS 或 Linux (Bash):**

    ```bash
    # 使用 Bash 脚本打包，并指定版本号
    ./local_build.sh v1.0.0
    ```

脚本会自动完成以下工作：
*   **构建 Docker 镜像**：基于 `Dockerfile` 创建包含所有代码和依赖的镜像。
*   **打包镜像**：将镜像保存为一个 `.tar` 文件，例如 `voice-log-app-v1.0.0.tar`。

打包完成后，您会在项目根目录下看到这个 `.tar` 文件。

---

## 🚀 第二部分：在云服务器上部署

现在，我们将把打包好的文件上传到您的 Linux 服务器并完成部署。

### 步骤 1：环境准备
请确保您的云服务器已经安装了：
-   [Docker Engine](https://docs.docker.com/engine/install/)
-   **Docker Compose V2**

### 步骤 2：上传必要文件
您 **只需要** 将以下 **4个文件** 上传到服务器的一个专用目录（例如 `/root/AI_Voice_Log`）。

1.  **打包好的镜像**：例如 `voice-log-app-v1.0.0.tar`
2.  **Docker Compose 配置文件**：`docker-compose.yml`
3.  **环境变量文件**：`.env`
4.  **部署脚本**：`server_deploy.sh`

您可以使用 `scp` 或任何 FTP 工具上传。`scp` 命令示例如下：
```bash
# 在本地终端中运行
scp voice-log-app-v1.0.0.tar docker-compose.yml .env server_deploy.sh root@your_server_ip:/root/AI_Voice_Log
```

### 步骤 3：连接到服务器并一键部署

1.  **登录服务器**：
    ```bash
    ssh root@your_server_ip
    ```

2.  **进入部署目录**：
    ```bash
    cd /root/AI_Voice_Log
    ```

3.  **为部署脚本添加执行权限** (首次部署需要):
    ```bash
    chmod +x server_deploy.sh
    ```

4.  **运行部署脚本**：
    ```bash
    # 将 .tar 文件名作为参数传入
    ./server_deploy.sh voice-log-app-v1.0.0.tar
    ```

脚本会自动、安全地完成所有操作：
*   **加载镜像**：从 `.tar` 文件加载 Docker 镜像。
*   **强制清理旧容器**：确保端口被释放。
*   **清理旧网络**：移除旧的容器网络。
*   **启动新版本**：在后台启动新的应用容器。

---

## 🚀 第三部分：验证、访问与排查

### 步骤 1：验证部署
部署脚本执行完毕后，运行以下命令确认容器状态：
```bash
docker ps
```
您应该能看到一个名为 `voice-log-app` 的容器，状态为 `Up`。

### 步骤 2：如何访问您的应用
部署成功后，应用即可通过服务器的公网 IP 和配置的端口访问。

-   **API 文档 (Swagger UI)**:
    `http://<your_server_ip>:<PORT>/docs`

-   **健康检查接口**:
    `http://<your_server_ip>:<PORT>/hello`

-   **实时查看日志**:
    ```bash
    docker compose logs -f
    ```

### 步骤 3：常见问题排查

-   **问题：`port is already allocated` (端口被占用)**
    -   **原因**：旧的容器没有被彻底移除。
    -   **解决方案**：`server_deploy.sh` 脚本已内置强制清理逻辑。如果问题依然存在，请手动查找并停止/移除占用端口的容器。

-   **问题：`docker-compose: command not found`**
    -   **原因**：服务器上安装的是新版本的 Docker，`docker-compose` 命令已被整合为 `docker compose`。
    -   **解决方案**：所有脚本和文档都已更新为使用 `docker compose`。

-   **问题：无法从外部访问应用**
    -   **原因**：服务器的防火墙或云服务商的安全组策略没有放行指定端口。
    -   **解决方案**：请在您的云服务控制台配置安全组规则，允许指定端口的 TCP 访问。

---

## 🚀 第四部分：如何测试与使用

### 步骤 1：找到项目入口

-   **项目主页**:
    `http://<your_server_ip>:<PORT>`

### 步骤 2：进行端到端测试

1.  **打开主页**
2.  **上传音频文件**
3.  **观察状态变化**
4.  **验证结果**：处理完成后，文件的状态会变为 **“处理完成”**，并展示 **“摘要总结”**。

### 步骤 3：API 专项测试 (面向开发者)

-   **API 文档 (Swagger UI)**:
    `http://<your_server_ip>:<PORT>/docs`

---

## 贡献

欢迎对本项目做出贡献！如果您有任何建议或发现任何问题，请随时提交 Pull Request 或 Issue。详情请参阅 `CONTRIBUTING.md`。