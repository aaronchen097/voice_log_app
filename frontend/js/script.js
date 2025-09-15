document.addEventListener("DOMContentLoaded", () => {
    // 如果当前是登录页面，则不执行后续的认证检查和功能初始化
    if (window.location.pathname === '/login' || window.location.pathname === '/login.html') {
        return;
    }
    // 检查用户登录状态
    if (!checkAuthStatus()) {
        return;
    }

    // DOM元素引用已移至需要时获取，避免页面加载时元素不存在的问题

    // 获取认证token
    function getAuthToken() {
        return localStorage.getItem('sessionToken') || '';
    }
    
    // 验证token有效性
    // Token验证缓存
    let tokenValidationCache = null;
    let tokenValidationTime = null;
    
    async function validateToken(useCache = true) {
        const token = getAuthToken();
        if (!token) {
            return false;
        }
        
        // 如果启用缓存且缓存有效（5分钟内），直接返回缓存结果
        if (useCache && tokenValidationCache !== null && tokenValidationTime) {
            const now = Date.now();
            const cacheAge = now - tokenValidationTime;
            if (cacheAge < 5 * 60 * 1000) { // 5分钟缓存
                console.log('使用缓存的token验证结果');
                return tokenValidationCache;
            }
        }
        
        try {
            console.log('执行token验证请求');
            const response = await fetch('/api/user/info', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            let isValid = false;
            if (response.ok) {
                isValid = true;
            } else if (response.status === 401) {
                // Token已过期或无效，清除本地存储
                console.log('Token已过期，清除会话信息');
                sessionStorage.removeItem('user_info');
                sessionStorage.removeItem('login_time');
                sessionStorage.removeItem('session_active');
                sessionStorage.removeItem('temp_user_info');
                localStorage.removeItem('sessionToken');
                isValid = false;
            }
            
            // 更新缓存
            if (useCache) {
                tokenValidationCache = isValid;
                tokenValidationTime = Date.now();
            }
            
            return isValid;
        } catch (error) {
            console.error('Token验证失败:', error);
            // 验证失败时不更新缓存，保持之前的状态
            return false;
        }
    }
    
    // 清除token验证缓存（在登出或token变更时调用）
    function clearTokenValidationCache() {
        tokenValidationCache = null;
        tokenValidationTime = null;
    }

    // 检查用户登录状态 - 支持会话持久化
    function checkAuthStatus() {
        console.log('checkAuthStatus: 开始检查认证状态');
        
        // 检查sessionStorage中的会话状态
        const sessionActive = sessionStorage.getItem('session_active');
        const userInfo = sessionStorage.getItem('user_info');
        const loginTime = sessionStorage.getItem('login_time');
        
        console.log('checkAuthStatus: sessionActive =', sessionActive);
        console.log('checkAuthStatus: userInfo =', userInfo);
        console.log('checkAuthStatus: loginTime =', loginTime);
        
        if (sessionActive && userInfo && loginTime) {
            // 检查会话是否过期（8小时）
            const loginDate = new Date(loginTime);
            const now = new Date();
            const timeDiff = (now - loginDate) / (1000 * 60 * 60); // 转换为小时
            
            if (timeDiff < 8) {
                console.log('checkAuthStatus: 发现有效会话，允许访问');
                // 保存用户信息用于显示
                sessionStorage.setItem('temp_user_info', userInfo);
                return true;
            } else {
                console.log('checkAuthStatus: 会话已过期，清除会话信息');
                // 会话过期，清除所有会话信息
                sessionStorage.removeItem('user_info');
                sessionStorage.removeItem('login_time');
                sessionStorage.removeItem('session_active');
                sessionStorage.removeItem('temp_user_info');
                localStorage.removeItem('sessionToken');
            }
        }
        
        console.log('checkAuthStatus: 没有有效会话，跳转到登录页面');
        // 没有有效的登录会话，跳转到登录页面
        window.location.href = '/login';
        return false;
    }
    
    // 显示用户状态栏
    function showUserStatus() {
        const userStatus = document.getElementById('userStatus');
        const username = document.getElementById('username');
        const userInfo = sessionStorage.getItem('temp_user_info');
        
        if (userInfo && userStatus) {
            try {
                const user = JSON.parse(userInfo);
                if (username) {
                    username.textContent = user.username || '用户';
                }
                userStatus.style.display = 'flex';
            } catch (error) {
                console.error('解析用户信息失败:', error);
            }
        }
    }
    
    // 退出登录功能
    function logout() {
        // 清除所有登录相关的存储信息
        localStorage.removeItem('user_info');
        localStorage.removeItem('login_time');
        localStorage.removeItem('sessionToken');
        sessionStorage.removeItem('user_info');
        sessionStorage.removeItem('login_time');
        sessionStorage.removeItem('session_active');
        sessionStorage.removeItem('temp_user_info');
        
        // 清除token验证缓存
        clearTokenValidationCache();
        
        // 跳转到登录页面
        window.location.href = '/login';
    }
    
    // 初始化用户界面
    function initUserInterface() {
        showUserStatus();
        
        // 绑定退出登录按钮事件
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', logout);
        }
    }
    
    // 调用初始化函数
    initUserInterface();
    
    // 新的文件上传元素
    // 获取实际存在的DOM元素
    const fileInput = document.getElementById("file-input");
    const uploadArea = document.getElementById("upload-area");
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // 其他元素在需要时动态获取，避免页面加载时不存在的问题

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let currentTranscription = '';
    
    // 任务管理器类
    class TaskManager {
        constructor() {
            this.tasks = new Map();
            this.activeUploads = 0;
            this.maxConcurrentUploads = 3;
        }
        
        // 创建新任务
        createTask(file) {
            const taskId = 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            const task = {
                id: taskId,
                filename: file.name,
                file: file,
                status: 'pending', // pending, uploading, processing, completed, failed
                progress: 0,
                startTime: Date.now(),
                element: null,
                result: null,
                error: null
            };
            
            this.tasks.set(taskId, task);
            this.createTaskElement(task);
            return task;
        }
        
        // 创建任务DOM元素
        createTaskElement(task) {
            const template = document.getElementById('task-progress-template');
            const tasksContainer = document.getElementById('tasks-container');
            const tasksSection = document.getElementById('tasks-section');
            
            if (!template || !tasksContainer) return;
            
            // 显示任务区域
            if (tasksSection) {
                tasksSection.classList.remove('hidden');
            }
            
            // 克隆模板
            const taskElement = template.content.cloneNode(true);
            const taskDiv = taskElement.querySelector('.task-progress');
            
            // 设置任务ID和文件名
            taskDiv.setAttribute('data-task-id', task.id);
            taskDiv.querySelector('.task-filename').textContent = task.filename;
            
            // 绑定折叠按钮事件
            const collapseBtn = taskDiv.querySelector('.task-collapse-btn');
            collapseBtn.addEventListener('click', () => this.toggleTaskCollapse(task.id));
            
            // 添加到容器
            tasksContainer.appendChild(taskElement);
            task.element = tasksContainer.querySelector(`[data-task-id="${task.id}"]`);
        }
        
        // 更新任务进度
        updateTaskProgress(taskId, progress, status, step) {
            const task = this.tasks.get(taskId);
            if (!task || !task.element) return;
            
            task.progress = progress;
            task.status = status;
            
            const element = task.element;
            const progressFill = element.querySelector('.progress-fill');
            const progressPercentage = element.querySelector('.progress-percentage');
            const taskStatus = element.querySelector('.task-status');
            const taskIcon = element.querySelector('.task-icon');
            const taskTimer = element.querySelector('.task-timer');
            
            // 更新进度条
            if (progressFill) progressFill.style.width = `${progress}%`;
            if (progressPercentage) progressPercentage.textContent = `${progress}%`;
            if (taskStatus) taskStatus.textContent = status;
            
            // 更新图标
            if (taskIcon) {
                if (progress === 100) {
                    taskIcon.textContent = '✅';
                } else if (progress > 0) {
                    taskIcon.textContent = '🔄';
                } else {
                    taskIcon.textContent = '⏳';
                }
            }
            
            // 更新计时器
            if (taskTimer) {
                const elapsed = Math.floor((Date.now() - task.startTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                const timeStr = minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`;
                taskTimer.textContent = timeStr;
            }
            
            // 更新步骤指示器
            this.updateTaskSteps(taskId, step, progress);
        }
        
        // 更新任务步骤指示器
        updateTaskSteps(taskId, currentStep, progress) {
            const task = this.tasks.get(taskId);
            if (!task || !task.element) return;
            
            const steps = task.element.querySelectorAll('.step');
            steps.forEach(step => {
                step.classList.remove('active', 'completed');
            });
            
            if (progress <= 30) {
                const uploadStep = task.element.querySelector('[data-step="upload"]');
                if (uploadStep) uploadStep.classList.add('active');
            } else if (progress <= 90) {
                const uploadStep = task.element.querySelector('[data-step="upload"]');
                const processStep = task.element.querySelector('[data-step="process"]');
                if (uploadStep) uploadStep.classList.add('completed');
                if (processStep) processStep.classList.add('active');
            } else {
                const uploadStep = task.element.querySelector('[data-step="upload"]');
                const processStep = task.element.querySelector('[data-step="process"]');
                const completeStep = task.element.querySelector('[data-step="complete"]');
                if (uploadStep) uploadStep.classList.add('completed');
                if (processStep) processStep.classList.add('completed');
                if (completeStep) completeStep.classList.add('active');
            }
        }
        
        // 完成任务
        completeTask(taskId, result) {
            const task = this.tasks.get(taskId);
            if (!task) return;
            
            task.result = result;
            task.status = 'completed';
            this.updateTaskProgress(taskId, 100, '✅ 转写完成', 'complete');
            
            // 隐藏结果预览，只显示进度条
            const resultDiv = task.element.querySelector('.task-result');
            if (resultDiv) {
                resultDiv.style.display = 'none';
            }
            
            this.activeUploads--;
            this.showClearCompletedButton();
        }
        
        // 任务失败
        failTask(taskId, error) {
            const task = this.tasks.get(taskId);
            if (!task) return;
            
            task.error = error;
            task.status = 'failed';
            this.updateTaskProgress(taskId, 0, `❌ 失败: ${error}`, 'upload');
            
            if (task.element) {
                const taskIcon = task.element.querySelector('.task-icon');
                if (taskIcon) taskIcon.textContent = '❌';
            }
            
            this.activeUploads--;
        }
        
        // 折叠/展开任务
        toggleTaskCollapse(taskId) {
            const task = this.tasks.get(taskId);
            if (!task || !task.element) return;
            
            const content = task.element.querySelector('.task-content');
            const collapseBtn = task.element.querySelector('.task-collapse-btn');
            
            if (content.style.display === 'none') {
                content.style.display = 'block';
                collapseBtn.textContent = '−';
            } else {
                content.style.display = 'none';
                collapseBtn.textContent = '+';
            }
        }
        
        // 显示完整结果
        showFullResult(taskId) {
            const task = this.tasks.get(taskId);
            if (!task || !task.result) return;
            
            // 更新主结果区域
            currentTranscription = task.result.text || '';
            if (transcriptionContent) {
                transcriptionContent.textContent = currentTranscription;
            }
            if (resultSection) {
                resultSection.classList.remove('hidden');
            }
            
            // 如果有摘要，显示摘要区域
            if (task.result.summary) {
                if (summaryResult) {
                    summaryResult.innerHTML = `<p>${task.result.summary}</p>`;
                }
                if (summarySection) {
                    summarySection.classList.remove('hidden');
                }
            }
        }
        
        // 显示清除已完成按钮
        showClearCompletedButton() {
            const completedTasks = Array.from(this.tasks.values()).filter(task => task.status === 'completed' || task.status === 'failed');
            const clearBtn = document.getElementById('clear-completed-btn');
            
            if (clearBtn && completedTasks.length > 0) {
                clearBtn.style.display = 'block';
                clearBtn.onclick = () => this.clearCompletedTasks();
            }
        }
        
        // 清除已完成的任务
        clearCompletedTasks() {
            const completedTasks = Array.from(this.tasks.values()).filter(task => task.status === 'completed' || task.status === 'failed');
            
            completedTasks.forEach(task => {
                if (task.element) {
                    task.element.remove();
                }
                this.tasks.delete(task.id);
            });
            
            const clearBtn = document.getElementById('clear-completed-btn');
            if (clearBtn) {
                clearBtn.style.display = 'none';
            }
            
            // 如果没有任务了，隐藏任务区域
            if (this.tasks.size === 0) {
                const tasksSection = document.getElementById('tasks-section');
                if (tasksSection) {
                    tasksSection.classList.add('hidden');
                }
            }
        }
        
        // 检查是否可以开始新的上传
        canStartNewUpload() {
            return this.activeUploads < this.maxConcurrentUploads;
        }
        
        // 开始上传
        startUpload(taskId) {
            this.activeUploads++;
            this.updateTaskProgress(taskId, 5, '准备上传...', 'upload');
        }
        
        // 缓存token验证结果
        async getCachedTokenValidation() {
            // 直接使用全局的validateToken函数，它已经包含了缓存逻辑
            return await validateToken(true);
        }
    }
    
    // 显示转录结果
    function displayTranscriptionResult(text) {
        const transcriptionContent = document.getElementById('transcription-content');
        const resultSection = document.getElementById('result-section');
        
        if (transcriptionContent) {
            transcriptionContent.textContent = text;
        }
        if (resultSection) {
            resultSection.classList.remove('hidden');
        }
        
        // 更新全局变量
        currentTranscription = text;
    }
    
    // 显示摘要结果
    function displaySummaryResult(summary) {
        const summaryResult = document.getElementById('summary-result');
        const summarySection = document.getElementById('summary-section');
        
        if (summaryResult) {
            summaryResult.innerHTML = `<p>${summary}</p>`;
        }
        if (summarySection) {
            summarySection.classList.remove('hidden');
        }
    }
    
    // 显示个人能力评估结果
    function displayCapabilityAssessment(assessment) {
        const capabilityContent = document.getElementById('capability-content');
        const capabilitySection = document.getElementById('capability-section');
        
        if (capabilityContent) {
            // 将评估结果按行分割并格式化显示
            const formattedAssessment = assessment.replace(/\n/g, '<br>');
            capabilityContent.innerHTML = `<div class="capability-result">${formattedAssessment}</div>`;
        }
        if (capabilitySection) {
            capabilitySection.classList.remove('hidden');
        }
    }
    
    // 创建全局任务管理器实例
    const taskManager = new TaskManager();

    // 标签页切换功能
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // 更新标签按钮状态
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 显示对应内容
            tabContents.forEach(content => {
                if (content.id === `${tabId}-tab`) {
                    content.classList.remove('hidden');
                } else {
                    content.classList.add('hidden');
                }
            });
        });
    });

    // 文件上传功能
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    
    if (uploadArea) {
        // 拖拽上传
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileUpload(files[0]);
            }
        });
    }

    // 处理文件选择
    function handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    }

    // 处理文件上传 - 使用TaskManager
    async function handleFileUpload(file) {
        // 验证文件类型
        const allowedTypes = ['audio/mp3', 'audio/wav', 'audio/m4a', 'audio/aac', 'audio/mpeg'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|aac)$/i)) {
            alert('请选择支持的音频格式：MP3, WAV, M4A, AAC');
            return;
        }

        // 验证文件大小 (500MB)
        if (file.size > 500 * 1024 * 1024) {
            alert('文件大小不能超过500MB');
            return;
        }

        // 检查是否可以开始新的上传
        if (!taskManager.canStartNewUpload()) {
            alert(`当前已有${taskManager.maxConcurrentUploads}个文件在处理中，请等待完成后再上传`);
            return;
        }

        // 创建新任务
        const task = taskManager.createTask(file);

        try {
            // 使用缓存的token验证
            taskManager.updateTaskProgress(task.id, 2, '验证登录状态...', 'upload');
            const isTokenValid = await taskManager.getCachedTokenValidation();
            if (!isTokenValid) {
                taskManager.failTask(task.id, '登录已过期，请重新登录');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                return;
            }

            // 开始上传
            taskManager.startUpload(task.id);

            const formData = new FormData();
            formData.append('file', file);
            
            taskManager.updateTaskProgress(task.id, 20, '正在上传文件...', 'upload');
            
            const response = await fetch('/api/voice_log', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                },
                body: formData
            });

            if (response.status === 401) {
                taskManager.failTask(task.id, '认证失败，请重新登录');
                // 清除缓存的token验证
                taskManager.tokenValidationCache = null;
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            taskManager.updateTaskProgress(task.id, 50, '文件上传完成，正在进行语音识别...', 'process');
            
            const result = await response.json();
            
            if (result.success) {
                taskManager.updateTaskProgress(task.id, 90, '转写完成，正在整理结果...', 'process');
                
                // 完成任务 - 修复缓存问题 v1.1
                taskManager.completeTask(task.id, {
                    text: result.text || '',
                    summary: result.summary || null,
                    capability_assessment: result.capability_assessment || null
                });
                
                // 显示转录结果
                if (result.text) {
                    displayTranscriptionResult(result.text);
                }
                
                // 显示摘要结果
                if (result.summary) {
                    displaySummaryResult(result.summary);
                }
                
                // 显示个人能力评估结果
                if (result.capability_assessment) {
                    displayCapabilityAssessment(result.capability_assessment);
                }
                
                // 自动生成摘要（如果没有的话）
                if (result.text && result.text.trim() && !result.summary) {
                    generateSummaryForTask(task.id, result.text);
                }
            } else {
                throw new Error(result.error || '转写失败');
            }

        } catch (error) {
            console.error('上传失败:', error);
            taskManager.failTask(task.id, error.message);
        }
    }

    // 更新进度显示
    // 兼容原有的updateProgress函数（用于向后兼容）
    function updateProgress(percent, message, step = null, taskId = null) {
        // 使用TaskManager更新任务进度
        if (taskId && window.taskManager) {
            window.taskManager.updateTaskProgress(taskId, percent, message, step);
        }
    }
    
    // updateProgressSteps函数已删除，现在使用TaskManager管理步骤状态
    
    // updateTimer函数已删除，现在使用TaskManager管理计时器

    // 显示成功提示消息
    function showSuccessMessage(message) {
        console.log('showSuccessMessage被调用，消息:', message);
        // 创建成功提示元素
        const successAlert = document.createElement('div');
        successAlert.className = 'success-alert';
        successAlert.innerHTML = `
            <div class="success-content">
                <span class="success-icon">✅</span>
                <span class="success-text">${message}</span>
                <button class="success-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
        `;
        
        // 添加样式
        successAlert.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
            display: block;
            visibility: visible;
            opacity: 1;
        `;
        console.log('成功提示样式已设置');
        
        // 添加动画样式
        if (!document.querySelector('#success-alert-styles')) {
            const style = document.createElement('style');
            style.id = 'success-alert-styles';
            style.textContent = `
                @keyframes slideIn {
                    0% { transform: translateX(100%); opacity: 0; }
                    100% { transform: translateX(0); opacity: 1; }
                }
                .success-alert {
                    transform: translateX(0) !important;
                    opacity: 1 !important;
                }
                .success-content {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    color: #155724;
                }
                .success-icon {
                    font-size: 18px;
                }
                .success-text {
                    flex: 1;
                    font-weight: 500;
                }
                .success-close {
                    background: none;
                    border: none;
                    font-size: 20px;
                    cursor: pointer;
                    color: #155724;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .success-close:hover {
                    background: rgba(21, 87, 36, 0.1);
                    border-radius: 50%;
                }
            `;
            document.head.appendChild(style);
        }
        
        // 添加到页面
        document.body.appendChild(successAlert);
        console.log('成功提示元素已添加到页面');
        
        // 3秒后自动消失
        setTimeout(() => {
            if (successAlert.parentElement) {
                successAlert.remove();
                console.log('成功提示元素已移除');
            }
        }, 3000);
    }

    // 为特定任务生成摘要
    async function generateSummaryForTask(taskId, text) {
        if (!text || text.trim() === '') {
            return;
        }
        
        const task = taskManager.tasks.get(taskId);
        if (!task) return;
        
        try {
            taskManager.updateTaskProgress(taskId, 95, '正在生成摘要...', 'process');
            
            const response = await fetch('/api/summary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${getAuthToken()}`
                },
                body: JSON.stringify({ text: text })
            });
            
            if (response.status === 401) {
                // 不影响主任务，只是摘要失败
                console.warn('摘要生成时认证失败');
                return;
            }
            
            if (!response.ok) {
                console.warn(`摘要生成失败: HTTP ${response.status}`);
                return;
            }
            
            const result = await response.json();
            
            if (result.success && result.summary) {
                // 更新任务结果
                task.result.summary = result.summary;
                
                // 更新任务显示
                const resultDiv = task.element.querySelector('.task-result');
                const resultPreview = task.element.querySelector('.result-preview');
                if (resultDiv && resultPreview) {
                    const preview = text.length > 100 ? text.substring(0, 100) + '...' : text;
                    resultPreview.textContent = `${preview}\n\n摘要: ${result.summary.substring(0, 50)}...`;
                }
            }
        } catch (error) {
            console.error('Summary generation error for task:', taskId, error);
            // 摘要失败不影响主任务
        }
    }
    
    // 生成摘要 - 兼容原有功能
    async function generateSummary(text) {
        if (!text || text.trim() === '') {
            alert('没有可用的转录文本来生成摘要');
            return;
        }
        
        if (summaryButton) {
            summaryButton.disabled = true;
            summaryButton.textContent = '生成中...';
        }
        
        try {
            const response = await fetch('/api/summary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${getAuthToken()}`
                },
                body: JSON.stringify({ text: text })
            });
            
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success && result.summary) {
                if (summaryResult) {
                    summaryResult.innerHTML = `<p>${result.summary}</p>`;
                }
                if (summarySection) {
                    summarySection.classList.remove('hidden');
                }
            } else {
                throw new Error(result.error || '摘要生成失败');
            }
        } catch (error) {
            console.error('Summary generation error:', error);
            alert(`摘要生成失败: ${error.message}`);
        } finally {
            if (summaryButton) {
                summaryButton.disabled = false;
                summaryButton.textContent = '生成摘要';
            }
        }
    }

    // 摘要功能现在由TaskManager自动处理，无需手动触发

    // 录音和查询功能已移除，当前版本专注于文件上传功能

    // 复制个人能力评估按钮事件
    const copyCapabilityBtn = document.getElementById('copy-capability-btn');
    if (copyCapabilityBtn) {
        copyCapabilityBtn.addEventListener('click', () => {
            const capabilityContent = document.getElementById('capability-content');
            if (capabilityContent) {
                const text = capabilityContent.textContent || capabilityContent.innerText;
                navigator.clipboard.writeText(text).then(() => {
                    showSuccessAlert('个人能力评估已复制到剪贴板');
                }).catch(err => {
                    console.error('复制失败:', err);
                    // 降级方案：选择文本
                    const range = document.createRange();
                    range.selectNodeContents(capabilityContent);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                });
            }
        });
    }

});