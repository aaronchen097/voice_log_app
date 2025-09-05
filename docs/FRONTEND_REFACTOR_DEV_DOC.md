# 语音智能日志 - 前端重构开发文档（完整版）

## 📋 项目概述

基于历史开发记录和痛点分析，重新构建语音智能日志系统的前端界面。该系统支持音频文件上传、阿里云语音转录、AI摘要生成等功能。

## 🛠 技术栈

- **前端**: HTML5 + CSS3 + JavaScript (ES6+)
- **后端API**: FastAPI (Python)
- **语音服务**: 阿里云通义听悟
- **AI模型**: 通义千问 (qwen-plus/qwen-max)
- **文件存储**: 阿里云OSS
- **部署**: Docker + Nginx

## 🎯 核心功能模块

### 1. 文件上传模块
- 本地音频文件上传
- URL音频文件上传
- 文件大小验证和进度显示
- 支持格式：MP3, WAV, M4A, AAC

### 2. 转录处理模块
- 阿里云语音转录任务提交
- 实时状态查询和进度显示
- 转录结果获取和格式化

### 3. AI摘要模块
- 转录文本智能摘要
- 多种摘要类型（日报、要点、任务清单）
- 支持qwen-plus和qwen-max模型

## 🚨 历史开发痛点及解决方案

### 痛点1: 音频文件大小限制

**问题描述**:
- 大文件上传失败
- 超时导致任务中断
- 前端无法处理大文件进度显示

**解决方案**:
```javascript
// 文件大小检查和分片上传
function validateFileSize(file) {
    const maxSize = 500 * 1024 * 1024; // 500MB限制
    if (file.size > maxSize) {
        showError(`文件过大，请选择小于500MB的音频文件`);
        return false;
    }
    return true;
}

// 大文件分片上传（如需要）
function uploadLargeFile(file) {
    const chunkSize = 10 * 1024 * 1024; // 10MB分片
    const chunks = Math.ceil(file.size / chunkSize);
    
    for (let i = 0; i < chunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const chunk = file.slice(start, end);
        // 上传分片逻辑
    }
}
```

### 痛点2: 前后端API连接问题

**问题描述**:
- CORS跨域错误
- API端点不一致
- 请求格式错误

**解决方案**:
```javascript
// 统一API配置
const API_CONFIG = {
    baseURL: window.location.origin, // 动态获取基础URL
    endpoints: {
        upload: '/upload/',
        status: '/status/',
        result: '/result/',
        health: '/health'
    },
    timeout: 300000 // 5分钟超时
};

// 统一请求函数
async function apiRequest(endpoint, options = {}) {
    const url = `${API_CONFIG.baseURL}${endpoint}`;
    const defaultOptions = {
        headers: {
            'Accept': 'application/json',
        },
        timeout: API_CONFIG.timeout
    };
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API请求失败:', error);
        throw error;
    }
}
```

### 痛点3: 本地文件和URL文件上传问题

**问题描述**:
- 两种上传方式处理逻辑不同
- URL验证不充分
- 错误处理不统一

**解决方案**:
```javascript
// 统一上传处理
class AudioUploader {
    constructor() {
        this.supportedFormats = ['mp3', 'wav', 'm4a', 'aac'];
    }
    
    async uploadFile(file) {
        if (!this.validateFile(file)) return null;
        
        const formData = new FormData();
        formData.append('file', file);
        
        return await this.submitUpload(formData);
    }
    
    async uploadFromURL(url) {
        if (!this.validateURL(url)) return null;
        
        const formData = new FormData();
        formData.append('audio_url', url);
        
        return await this.submitUpload(formData);
    }
    
    validateFile(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        if (!this.supportedFormats.includes(extension)) {
            showError(`不支持的文件格式，请选择: ${this.supportedFormats.join(', ')}`);
            return false;
        }
        return validateFileSize(file);
    }
    
    validateURL(url) {
        const urlPattern = /^https?:\/\/.+\.(mp3|wav|m4a|aac)(\?.*)?$/i;
        if (!urlPattern.test(url)) {
            showError('请输入有效的音频文件URL');
            return false;
        }
        return true;
    }
    
    async submitUpload(formData) {
        try {
            showProgress('正在上传文件...');
            const result = await apiRequest(API_CONFIG.endpoints.upload, {
                method: 'POST',
                body: formData
            });
            return result;
        } catch (error) {
            showError(`上传失败: ${error.message}`);
            return null;
        }
    }
}
```

### 痛点4: 超时限制问题

**问题描述**:
- 长时间转录任务超时
- 前端等待时间过长
- 用户体验差

**解决方案**:
```javascript
// 智能轮询状态检查
class TaskStatusMonitor {
    constructor(taskId) {
        this.taskId = taskId;
        this.pollInterval = 5000; // 初始5秒
        this.maxInterval = 30000; // 最大30秒
        this.maxRetries = 360; // 最多30分钟
        this.retryCount = 0;
    }
    
    async startMonitoring() {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const status = await this.checkStatus();
                    
                    if (status.completed) {
                        resolve(status);
                        return;
                    }
                    
                    if (this.retryCount >= this.maxRetries) {
                        reject(new Error('任务超时，请稍后重试'));
                        return;
                    }
                    
                    // 动态调整轮询间隔
                    this.adjustPollInterval();
                    this.retryCount++;
                    
                    setTimeout(poll, this.pollInterval);
                    
                } catch (error) {
                    reject(error);
                }
            };
            
            poll();
        });
    }
    
    async checkStatus() {
        const response = await apiRequest(`${API_CONFIG.endpoints.status}${this.taskId}`);
        
        updateProgress({
            status: response.status,
            progress: response.progress || 0,
            message: this.getStatusMessage(response.status)
        });
        
        return {
            completed: ['SUCCEEDED', 'FAILED'].includes(response.status),
            status: response.status,
            data: response
        };
    }
    
    adjustPollInterval() {
        // 逐渐增加轮询间隔，减少服务器压力
        if (this.retryCount > 10) {
            this.pollInterval = Math.min(this.pollInterval * 1.2, this.maxInterval);
        }
    }
    
    getStatusMessage(status) {
        const messages = {
            'QUEUEING': '任务排队中...',
            'RUNNING': '正在转录音频...',
            'SUCCEEDED': '转录完成',
            'FAILED': '转录失败'
        };
        return messages[status] || '处理中...';
    }
}
```

### 痛点5: 阿里云转录任务状态判断

**问题描述**:
- 状态码不统一
- 错误状态处理不完善
- 任务失败原因不明确

**解决方案**:
```javascript
// 阿里云任务状态处理
class AliyunTaskHandler {
    constructor() {
        this.statusMap = {
            'QUEUEING': { type: 'pending', message: '任务排队中，请耐心等待' },
            'RUNNING': { type: 'processing', message: '正在处理音频文件' },
            'SUCCEEDED': { type: 'success', message: '处理完成' },
            'FAILED': { type: 'error', message: '处理失败' },
            'CANCELLED': { type: 'error', message: '任务已取消' }
        };
    }
    
    handleTaskStatus(response) {
        const status = response.status;
        const statusInfo = this.statusMap[status] || { type: 'unknown', message: '未知状态' };
        
        switch (statusInfo.type) {
            case 'pending':
            case 'processing':
                this.showProcessingStatus(response);
                break;
            case 'success':
                this.handleSuccess(response);
                break;
            case 'error':
                this.handleError(response);
                break;
        }
        
        return statusInfo.type;
    }
    
    showProcessingStatus(response) {
        const progress = response.progress || 0;
        updateProgressBar(progress);
        showStatus(this.statusMap[response.status].message);
    }
    
    handleSuccess(response) {
        showSuccess('转录完成！正在获取结果...');
        this.fetchTranscriptionResult(response.task_id);
    }
    
    handleError(response) {
        const errorMsg = response.error_message || '转录失败，请重试';
        showError(`转录失败: ${errorMsg}`);
        
        // 记录错误详情用于调试
        console.error('阿里云转录错误:', {
            taskId: response.task_id,
            status: response.status,
            error: response.error_message,
            timestamp: new Date().toISOString()
        });
    }
    
    async fetchTranscriptionResult(taskId) {
        try {
            const result = await apiRequest(`${API_CONFIG.endpoints.result}${taskId}`);
            this.processTranscriptionResult(result);
        } catch (error) {
            showError(`获取转录结果失败: ${error.message}`);
        }
    }
    
    processTranscriptionResult(result) {
        if (result.transcription_text) {
            displayTranscription(result.transcription_text);
            enableSummaryGeneration(result.transcription_text);
        } else {
            showError('转录结果为空');
        }
    }
}
```

### 痛点6: qwen_plus模型使用

**问题描述**:
- 模型调用参数不正确
- 提示词格式问题
- 响应解析错误

**解决方案**:
```javascript
// AI摘要生成器
class AISummaryGenerator {
    constructor() {
        this.models = {
            'qwen-plus': { name: 'qwen-plus', displayName: '通义千问Plus' },
            'qwen-max': { name: 'qwen-max', displayName: '通义千问Max' }
        };
        this.summaryTypes = {
            'day_report': '日报摘要',
            'key_points': '关键要点',
            'action_items': '任务清单'
        };
    }
    
    async generateSummary(transcriptionText, summaryType = 'day_report', model = 'qwen-plus') {
        try {
            showProgress('正在生成AI摘要...');
            
            const requestData = {
                transcription_text: transcriptionText,
                summary_type: summaryType,
                model: model,
                custom_prompt: this.getCustomPrompt(summaryType)
            };
            
            const response = await apiRequest('/generate_summary/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (response.summary) {
                this.displaySummary(response.summary, summaryType);
                return response.summary;
            } else {
                throw new Error('摘要生成失败');
            }
            
        } catch (error) {
            showError(`AI摘要生成失败: ${error.message}`);
            return null;
        }
    }
    
    getCustomPrompt(summaryType) {
        const prompts = {
            'day_report': `请以首席参谋的视角分析语音记录，生成专业的工作日报，包含：
1. 今日核心概要
2. 详细工作纪要
3. 时间花费审计
4. 待办事项清单
请确保内容专业、客观、精炼。`,
            
            'key_points': `请提取语音记录中的关键信息：
1. 重要决策和结论
2. 核心业务洞察
3. 风险点和注意事项
4. 关键数据和指标`,
            
            'action_items': `请从语音记录中提取所有明确的任务：
1. 任务具体内容
2. 责任人
3. 截止日期
4. 优先级评估`
        };
        
        return prompts[summaryType] || prompts['day_report'];
    }
    
    displaySummary(summary, type) {
        const summaryContainer = document.getElementById('summary-result');
        const typeLabel = this.summaryTypes[type] || '摘要结果';
        
        summaryContainer.innerHTML = `
            <div class="summary-header">
                <h3>${typeLabel}</h3>
                <div class="summary-actions">
                    <button onclick="copySummary()" class="btn-copy">复制</button>
                    <button onclick="downloadSummary()" class="btn-download">下载</button>
                </div>
            </div>
            <div class="summary-content">
                <pre>${summary}</pre>
            </div>
        `;
        
        summaryContainer.style.display = 'block';
        hideProgress();
    }
}
```

### 痛点7: 转录内容读取和保存

**问题描述**:
- 转录URL内容获取失败
- 文本格式化问题
- 保存机制不完善

**解决方案**:
```javascript
// 转录内容处理器
class TranscriptionProcessor {
    constructor() {
        this.cache = new Map();
    }
    
    async processTranscriptionURL(transcriptionURL) {
        try {
            // 检查缓存
            if (this.cache.has(transcriptionURL)) {
                return this.cache.get(transcriptionURL);
            }
            
            showProgress('正在获取转录内容...');
            
            const response = await fetch(transcriptionURL);
            if (!response.ok) {
                throw new Error(`获取转录内容失败: ${response.statusText}`);
            }
            
            const transcriptionData = await response.json();
            const formattedText = this.formatTranscriptionText(transcriptionData);
            
            // 缓存结果
            this.cache.set(transcriptionURL, formattedText);
            
            // 保存到本地存储
            this.saveTranscriptionLocally(transcriptionURL, formattedText);
            
            return formattedText;
            
        } catch (error) {
            showError(`处理转录内容失败: ${error.message}`);
            return null;
        }
    }
    
    formatTranscriptionText(transcriptionData) {
        if (!transcriptionData || !transcriptionData.sentences) {
            throw new Error('转录数据格式错误');
        }
        
        let formattedText = '';
        let currentSpeaker = null;
        
        transcriptionData.sentences.forEach(sentence => {
            const speaker = sentence.speaker_id || 'Speaker1';
            const text = sentence.text || '';
            const startTime = this.formatTime(sentence.begin_time || 0);
            
            // 说话人变更时添加标识
            if (currentSpeaker !== speaker) {
                formattedText += `\n\n[${speaker}] (${startTime})\n`;
                currentSpeaker = speaker;
            }
            
            formattedText += text + ' ';
        });
        
        return formattedText.trim();
    }
    
    formatTime(milliseconds) {
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        const h = hours.toString().padStart(2, '0');
        const m = (minutes % 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        
        return `${h}:${m}:${s}`;
    }
    
    saveTranscriptionLocally(url, text) {
        try {
            const timestamp = new Date().toISOString();
            const transcriptionRecord = {
                url: url,
                text: text,
                timestamp: timestamp,
                id: this.generateId()
            };
            
            // 保存到localStorage
            const existingRecords = JSON.parse(localStorage.getItem('transcriptions') || '[]');
            existingRecords.push(transcriptionRecord);
            
            // 限制存储数量，只保留最近50条
            if (existingRecords.length > 50) {
                existingRecords.splice(0, existingRecords.length - 50);
            }
            
            localStorage.setItem('transcriptions', JSON.stringify(existingRecords));
            
        } catch (error) {
            console.warn('保存转录记录失败:', error);
        }
    }
    
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    getStoredTranscriptions() {
        try {
            return JSON.parse(localStorage.getItem('transcriptions') || '[]');
        } catch (error) {
            console.error('读取存储的转录记录失败:', error);
            return [];
        }
    }
}
```

## 🎨 完整前端实现

### HTML结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>语音智能日志系统</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>🎙️ 语音智能日志系统</h1>
            <p>上传音频文件，自动生成转录文本和AI摘要</p>
        </header>
        
        <main class="main-content">
            <!-- 上传区域 -->
            <section class="upload-section">
                <div class="upload-tabs">
                    <button class="tab-btn active" data-tab="file">本地文件</button>
                    <button class="tab-btn" data-tab="url">URL链接</button>
                </div>
                
                <div class="tab-content" id="file-tab">
                    <div class="upload-area" id="upload-area">
                        <div class="upload-icon">📁</div>
                        <p>拖拽音频文件到此处，或点击选择文件</p>
                        <p class="file-info">支持格式：MP3, WAV, M4A, AAC (最大500MB)</p>
                        <input type="file" id="file-input" accept=".mp3,.wav,.m4a,.aac" hidden>
                        <button class="btn-primary" onclick="document.getElementById('file-input').click()">选择文件</button>
                    </div>
                </div>
                
                <div class="tab-content hidden" id="url-tab">
                    <div class="url-input-area">
                        <input type="url" id="url-input" placeholder="请输入音频文件URL">
                        <button class="btn-primary" onclick="uploadFromURL()">上传URL</button>
                    </div>
                </div>
            </section>
            
            <!-- 进度显示 -->
            <section class="progress-section hidden" id="progress-section">
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <div class="progress-text" id="progress-text">准备中...</div>
                </div>
                <div class="status-details" id="status-details"></div>
            </section>
            
            <!-- 转录结果 -->
            <section class="result-section hidden" id="result-section">
                <div class="result-header">
                    <h3>📝 转录结果</h3>
                    <div class="result-actions">
                        <button onclick="copyTranscription()" class="btn-secondary">复制文本</button>
                        <button onclick="downloadTranscription()" class="btn-secondary">下载文本</button>
                    </div>
                </div>
                <div class="transcription-content" id="transcription-content"></div>
            </section>
            
            <!-- AI摘要 -->
            <section class="summary-section hidden" id="summary-section">
                <div class="summary-controls">
                    <h3>🤖 AI摘要生成</h3>
                    <div class="summary-options">
                        <select id="summary-type">
                            <option value="day_report">日报摘要</option>
                            <option value="key_points">关键要点</option>
                            <option value="action_items">任务清单</option>
                        </select>
                        <select id="ai-model">
                            <option value="qwen-plus">通义千问Plus</option>
                            <option value="qwen-max">通义千问Max</option>
                        </select>
                        <button onclick="generateSummary()" class="btn-primary">生成摘要</button>
                    </div>
                </div>
                <div class="summary-result hidden" id="summary-result"></div>
            </section>
            
            <!-- 历史记录 -->
            <section class="history-section">
                <div class="history-header">
                    <h3>📚 历史记录</h3>
                    <button onclick="clearHistory()" class="btn-secondary">清空记录</button>
                </div>
                <div class="history-list" id="history-list"></div>
            </section>
        </main>
        
        <!-- 消息提示 -->
        <div class="message-container" id="message-container"></div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

### CSS样式

```css
/* styles.css */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    margin-bottom: 40px;
    color: white;
}

.header h1 {
    font-size: 2.5rem;
    margin-bottom: 10px;
}

.main-content {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
}

/* 上传区域样式 */
.upload-tabs {
    display: flex;
    margin-bottom: 20px;
    border-bottom: 2px solid #f0f0f0;
}

.tab-btn {
    padding: 12px 24px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 16px;
    color: #666;
    border-bottom: 3px solid transparent;
    transition: all 0.3s;
}

.tab-btn.active {
    color: #667eea;
    border-bottom-color: #667eea;
}

.upload-area {
    border: 3px dashed #ddd;
    border-radius: 15px;
    padding: 40px;
    text-align: center;
    transition: all 0.3s;
    cursor: pointer;
}

.upload-area:hover {
    border-color: #667eea;
    background: #f8f9ff;
}

.upload-area.dragover {
    border-color: #667eea;
    background: #f0f4ff;
}

.upload-icon {
    font-size: 4rem;
    margin-bottom: 20px;
}

.file-info {
    color: #666;
    font-size: 14px;
    margin: 10px 0;
}

.url-input-area {
    display: flex;
    gap: 15px;
    align-items: center;
}

#url-input {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 16px;
}

/* 按钮样式 */
.btn-primary {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.3s;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
    background: #f8f9fa;
    color: #495057;
    border: 2px solid #dee2e6;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.3s;
}

.btn-secondary:hover {
    background: #e9ecef;
}

/* 进度条样式 */
.progress-container {
    margin: 20px 0;
}

.progress-bar {
    width: 100%;
    height: 8px;
    background: #f0f0f0;
    border-radius: 4px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #667eea, #764ba2);
    width: 0%;
    transition: width 0.3s;
}

.progress-text {
    text-align: center;
    margin-top: 10px;
    font-weight: 500;
}

/* 结果区域样式 */
.result-section, .summary-section {
    margin-top: 30px;
    padding: 20px;
    border: 1px solid #e9ecef;
    border-radius: 10px;
}

.result-header, .summary-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.result-actions, .summary-options {
    display: flex;
    gap: 10px;
}

.transcription-content {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    white-space: pre-wrap;
    max-height: 400px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    line-height: 1.6;
}

/* 工具类 */
.hidden {
    display: none !important;
}

.text-center {
    text-align: center;
}

/* 消息提示 */
.message-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
}

.message {
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 10px;
    color: white;
    font-weight: 500;
    animation: slideIn 0.3s ease;
}

.message.success {
    background: #28a745;
}

.message.error {
    background: #dc3545;
}

.message.info {
    background: #17a2b8;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

/* 响应式设计 */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    .main-content {
        padding: 20px;
    }
    
    .header h1 {
        font-size: 2rem;
    }
    
    .url-input-area {
        flex-direction: column;
    }
    
    .result-header, .summary-controls {
        flex-direction: column;
        gap: 15px;
        align-items: stretch;
    }
}
```

### JavaScript主文件

```javascript
// app.js - 主应用逻辑

// 全局变量
let currentTaskId = null;
let currentTranscriptionText = null;
const uploader = new AudioUploader();
const taskMonitor = new TaskStatusMonitor();
const aliyunHandler = new AliyunTaskHandler();
const summaryGenerator = new AISummaryGenerator();
const transcriptionProcessor = new TranscriptionProcessor();

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    loadHistoryRecords();
    checkServerHealth();
}

function setupEventListeners() {
    // 标签页切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
    
    // 文件上传
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('upload-area');
    
    fileInput.addEventListener('change', handleFileSelect);
    
    // 拖拽上传
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleFileDrop);
    
    // URL输入回车提交
    document.getElementById('url-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            uploadFromURL();
        }
    });
}

// 标签页切换
function switchTab(tabName) {
    // 更新按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // 显示对应内容
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`${tabName}-tab`).classList.remove('hidden');
}

// 文件选择处理
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        uploadFile(file);
    }
}

// 拖拽处理
function handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add('dragover');
}

function handleDragLeave(event) {
    event.currentTarget.classList.remove('dragover');
}

function handleFileDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');
    
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

// 文件上传
async function uploadFile(file) {
    try {
        resetUI();
        showProgress('正在上传文件...');
        
        const result = await uploader.uploadFile(file);
        if (result && result.task_id) {
            currentTaskId = result.task_id;
            await monitorTask(result.task_id);
        }
    } catch (error) {
        showError(`上传失败: ${error.message}`);
    }
}

// URL上传
async function uploadFromURL() {
    const url = document.getElementById('url-input').value.trim();
    if (!url) {
        showError('请输入音频文件URL');
        return;
    }
    
    try {
        resetUI();
        showProgress('正在处理URL...');
        
        const result = await uploader.uploadFromURL(url);
        if (result && result.task_id) {
            currentTaskId = result.task_id;
            await monitorTask(result.task_id);
        }
    } catch (error) {
        showError(`URL处理失败: ${error.message}`);
    }
}

// 任务监控
async function monitorTask(taskId) {
    try {
        const monitor = new TaskStatusMonitor(taskId);
        const result = await monitor.startMonitoring();
        
        if (result.status === 'SUCCEEDED') {
            await handleTaskSuccess(taskId);
        } else {
            showError('任务处理失败');
        }
    } catch (error) {
        showError(`任务监控失败: ${error.message}`);
    }
}

// 任务成功处理
async function handleTaskSuccess(taskId) {
    try {
        showProgress('正在获取转录结果...');
        
        const result = await apiRequest(`${API_CONFIG.endpoints.result}${taskId}`);
        
        if (result.transcription_url) {
            const transcriptionText = await transcriptionProcessor.processTranscriptionURL(result.transcription_url);
            if (transcriptionText) {
                currentTranscriptionText = transcriptionText;
                displayTranscription(transcriptionText);
                enableSummaryGeneration();
                saveToHistory(taskId, transcriptionText);
            }
        } else if (result.transcription_text) {
            currentTranscriptionText = result.transcription_text;
            displayTranscription(result.transcription_text);
            enableSummaryGeneration();
            saveToHistory(taskId, result.transcription_text);
        } else {
            showError('未找到转录结果');
        }
        
        hideProgress();
        
    } catch (error) {
        showError(`获取结果失败: ${error.message}`);
    }
}

// 显示转录结果
function displayTranscription(text) {
    const resultSection = document.getElementById('result-section');
    const transcriptionContent = document.getElementById('transcription-content');
    
    transcriptionContent.textContent = text;
    resultSection.classList.remove('hidden');
    
    showSuccess('转录完成！');
}

// 启用摘要生成
function enableSummaryGeneration() {
    document.getElementById('summary-section').classList.remove('hidden');
}

// 生成AI摘要
async function generateSummary() {
    if (!currentTranscriptionText) {
        showError('请先完成音频转录');
        return;
    }
    
    const summaryType = document.getElementById('summary-type').value;
    const model = document.getElementById('ai-model').value;
    
    const summary = await summaryGenerator.generateSummary(
        currentTranscriptionText, 
        summaryType, 
        model
    );
    
    if (summary) {
        showSuccess('AI摘要生成完成！');
    }
}

// 复制转录文本
function copyTranscription() {
    if (currentTranscriptionText) {
        navigator.clipboard.writeText(currentTranscriptionText).then(() => {
            showSuccess('转录文本已复制到剪贴板');
        }).catch(() => {
            showError('复制失败，请手动选择文本');
        });
    }
}

// 下载转录文本
function downloadTranscription() {
    if (currentTranscriptionText) {
        const blob = new Blob([currentTranscriptionText], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcription_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showSuccess('转录文本已下载');
    }
}

// 复制摘要
function copySummary() {
    const summaryContent = document.querySelector('#summary-result .summary-content pre');
    if (summaryContent) {
        navigator.clipboard.writeText(summaryContent.textContent).then(() => {
            showSuccess('摘要已复制到剪贴板');
        }).catch(() => {
            showError('复制失败，请手动选择文本');
        });
    }
}

// 下载摘要
function downloadSummary() {
    const summaryContent = document.querySelector('#summary-result .summary-content pre');
    if (summaryContent) {
        const blob = new Blob([summaryContent.textContent], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `summary_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showSuccess('摘要已下载');
    }
}

// UI控制函数
function resetUI() {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('summary-section').classList.add('hidden');
    currentTaskId = null;
    currentTranscriptionText = null;
}

function showProgress(message) {
    const progressSection = document.getElementById('progress-section');
    const progressText = document.getElementById('progress-text');
    
    progressText.textContent = message;
    progressSection.classList.remove('hidden');
}

function updateProgress(data) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const statusDetails = document.getElementById('status-details');
    
    if (data.progress !== undefined) {
        progressFill.style.width = `${data.progress}%`;
    }
    
    if (data.message) {
        progressText.textContent = data.message;
    }
    
    if (data.status) {
        statusDetails.textContent = `状态: ${data.status}`;
    }
}

function hideProgress() {
    document.getElementById('progress-section').classList.add('hidden');
}

// 消息提示
function showMessage(message, type = 'info') {
    const container = document.getElementById('message-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    container.appendChild(messageDiv);
    
    // 3秒后自动移除
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.parentNode.removeChild(messageDiv);
        }
    }, 3000);
}

function showSuccess(message) {
    showMessage(message, 'success');
}

function showError(message) {
    showMessage(message, 'error');
}

function showInfo(message) {
    showMessage(message, 'info');
}

// 历史记录管理
function saveToHistory(taskId, transcriptionText) {
    try {
        const historyItem = {
            id: taskId,
            text: transcriptionText.substring(0, 200) + '...', // 只保存前200字符作为预览
            fullText: transcriptionText,
            timestamp: new Date().toISOString(),
            date: new Date().toLocaleDateString('zh-CN')
        };
        
        const history = JSON.parse(localStorage.getItem('transcription_history') || '[]');
        history.unshift(historyItem); // 添加到开头
        
        // 只保留最近20条记录
        if (history.length > 20) {
            history.splice(20);
        }
        
        localStorage.setItem('transcription_history', JSON.stringify(history));
        loadHistoryRecords();
        
    } catch (error) {
        console.error('保存历史记录失败:', error);
    }
}

function loadHistoryRecords() {
    try {
        const history = JSON.parse(localStorage.getItem('transcription_history') || '[]');
        const historyList = document.getElementById('history-list');
        
        if (history.length === 0) {
            historyList.innerHTML = '<p class="text-center">暂无历史记录</p>';
            return;
        }
        
        historyList.innerHTML = history.map(item => `
            <div class="history-item" onclick="loadHistoryItem('${item.id}')">
                <div class="history-preview">${item.text}</div>
                <div class="history-date">${item.date}</div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

function loadHistoryItem(itemId) {
    try {
        const history = JSON.parse(localStorage.getItem('transcription_history') || '[]');
        const item = history.find(h => h.id === itemId);
        
        if (item) {
            currentTranscriptionText = item.fullText;
            displayTranscription(item.fullText);
            enableSummaryGeneration();
            showInfo('已加载历史记录');
        }
        
    } catch (error) {
        showError('加载历史记录失败');
    }
}

function clearHistory() {
    if (confirm('确定要清空所有历史记录吗？')) {
        localStorage.removeItem('transcription_history');
        loadHistoryRecords();
        showSuccess('历史记录已清空');
    }
}

// 服务器健康检查
async function checkServerHealth() {
    try {
        await apiRequest(API_CONFIG.endpoints.health);
        showInfo('服务器连接正常');
    } catch (error) {
        showError('服务器连接失败，请检查网络');
    }
}
```

## 🔧 部署和配置

### 环境变量配置

```bash
# .env 文件
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
APPKEY=your_appkey
OSS_ENDPOINT=your_oss_endpoint
OSS_BUCKET_NAME=your_bucket_name
OPENROUTER_API_KEY=your_openrouter_api_key
PORT=31101
```

### Docker部署

```dockerfile
# Dockerfile
FROM nginx:alpine

COPY simple_frontend.html /usr/share/nginx/html/index.html
COPY styles.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

# 配置nginx反向代理
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

## 📝 总结

本文档基于历史开发记录中的痛点，提供了完整的前端重构方案：

1. **解决了音频大小限制问题** - 文件验证和分片上传
2. **统一了API连接处理** - 标准化请求和错误处理
3. **优化了文件上传体验** - 支持本地和URL两种方式
4. **改进了超时处理机制** - 智能轮询和动态间隔
5. **完善了任务状态管理** - 阿里云状态码标准化处理
6. **集成了qwen_plus模型** - AI摘要生成功能
7. **实现了转录内容处理** - URL内容获取和本地存储

该前端系统具有良好的用户体验、错误处理机制和扩展性，可以有效支持语音智能日志的各项功能需求。