// 获取认证token - 移到全局作用域
function getAuthToken() {
    return localStorage.getItem('sessionToken') || '';
}

document.addEventListener("DOMContentLoaded", () => {
    // 如果当前是登录页面，则不执行后续的认证检查和功能初始化
    if (window.location.pathname === '/login' || window.location.pathname === '/login.html') {
        return;
    }
    // 检查用户登录状态
    if (!checkAuthStatus()) {
        return;
    }

    // 批量模式相关变量（现在只有批量模式）
    let batchSegments = [];
    
    // DOM元素引用已移至需要时获取，避免页面加载时元素不存在的问题
    
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
            this.updateTaskProgress(taskId, 100, '✅ 任务完成，等待飞书后台推送', 'complete');
            
            // 显示完成状态，不显示具体内容
            const resultDiv = task.element.querySelector('.task-result');
            const resultPreview = task.element.querySelector('.result-preview');
            if (resultDiv && resultPreview) {
                resultPreview.textContent = '转录完成，结果已保存到飞书多维表格';
                resultDiv.style.display = 'block';
                // 隐藏查看完整结果按钮
                const viewBtn = resultDiv.querySelector('.view-result-btn');
                if (viewBtn) viewBtn.style.display = 'none';
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
        
        // 显示完整结果 - 不再显示具体内容
        showFullResult(taskId) {
            const task = this.tasks.get(taskId);
            if (!task || !task.result) return;
            
            // 不显示具体的转写内容，只显示提示信息
            showSuccessMessage('转录结果已保存到飞书多维表格，请前往飞书查看详细内容');
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

    // 主人声管理功能
    async function checkMasterVoiceStatus() {
        try {
            const token = getAuthToken();
            if (!token) return false;
            
            const response = await fetch('/api/check_master_voice', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                updateMasterVoiceUI(data.has_master_voice, data.master_voice_file);
                return data.has_master_voice;
            }
        } catch (error) {
            console.error('检查主人声状态失败:', error);
        }
        return false;
    }
    
    function updateMasterVoiceUI(exists, filename = '') {
        const statusDiv = document.getElementById('master-voice-status');
        const uploadBtn = document.getElementById('upload-master-voice-btn');
        const deleteBtn = document.getElementById('delete-master-voice-btn');
        
        if (statusDiv) {
            if (exists) {
                statusDiv.innerHTML = `<span class="status-success">✓ 已设置主人声音频${filename ? ': ' + filename : ''}</span>`;
                if (uploadBtn) uploadBtn.textContent = '重新上传主人声';
                if (deleteBtn) deleteBtn.style.display = 'inline-block';
                // 隐藏提醒信息
                hideMasterVoiceReminder();
            } else {
                statusDiv.innerHTML = `<span class="status-warning">⚠ 未设置主人声音频</span>`;
                if (uploadBtn) uploadBtn.textContent = '上传主人声';
                if (deleteBtn) deleteBtn.style.display = 'none';
                // 显示提醒信息
                showMasterVoiceReminder();
            }
        }
    }
    
    function showMasterVoiceReminder() {
        // 检查是否已存在提醒
        let reminder = document.getElementById('master-voice-reminder');
        if (reminder) return;
        
        // 创建提醒元素
        reminder = document.createElement('div');
        reminder.id = 'master-voice-reminder';
        reminder.className = 'alert alert-warning mt-3';
        reminder.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div class="flex-grow-1">
                    <strong>重要提醒：</strong>您还没有上传主人声音频！<br>
                    <small class="text-muted">主人声音频用于语音克隆，请先上传您的声音样本以获得更好的效果。</small>
                </div>
                <button type="button" class="btn btn-primary btn-sm ms-2" onclick="document.getElementById('upload-master-voice-btn').click()">
                    立即上传
                </button>
            </div>
        `;
        
        // 插入到主人声设置区域
        const masterVoiceSection = document.querySelector('.tab-content #master-voice');
        if (masterVoiceSection) {
            const firstChild = masterVoiceSection.firstElementChild;
            if (firstChild) {
                masterVoiceSection.insertBefore(reminder, firstChild);
            } else {
                masterVoiceSection.appendChild(reminder);
            }
        }
    }
    
    function hideMasterVoiceReminder() {
        const reminder = document.getElementById('master-voice-reminder');
        if (reminder) {
            reminder.remove();
        }
    }
    
    async function uploadMasterVoice() {
        const input = document.getElementById('master-voice-input');
        if (!input) return;
        
        // 触发文件选择器
        input.click();
    }
    
    // 处理主人声文件选择
    async function handleMasterVoiceFileSelect(e) {
        const input = e.target;
        if (!input) return;
        
        const handleFileUpload = async () => {
            const file = e.target.files[0];
            if (!file) return;
            
            // 验证文件类型
            const allowedTypes = ['audio/mp3', 'audio/wav', 'audio/m4a', 'audio/aac', 'audio/mpeg'];
            if (!allowedTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|aac)$/i)) {
                showErrorAlert('请选择支持的音频格式：MP3, WAV, M4A, AAC');
                return;
            }
            
            // 验证文件大小（限制为10MB）
            if (file.size > 10 * 1024 * 1024) {
                showErrorAlert('文件大小不能超过10MB');
                return;
            }
            
            try {
                const token = getAuthToken();
                if (!token) {
                    showErrorAlert('请先登录');
                    return;
                }
                
                showSuccessAlert('正在上传主人声音频...');
                
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/api/upload_master_voice', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
                    body: formData
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        showSuccessAlert('主人声音频上传成功！');
                        // 重新检查状态以确保数据同步
                        await checkMasterVoiceStatus();
                    } else {
                        showErrorAlert(data.error || '上传失败');
                    }
                } else {
                    const errorData = await response.json();
                    showErrorAlert(errorData.error || '上传请求失败');
                }
            } catch (error) {
                console.error('上传主人声失败:', error);
                showErrorAlert('上传过程中发生错误');
            } finally {
                // 清空文件输入，允许重新选择同一文件
                input.value = '';
            }
        };
        
        await handleFileUpload();
    }
    
    async function deleteMasterVoice() {
        if (!confirm('确定要删除主人声音频吗？删除后将无法使用主人声预处理功能。')) {
            return;
        }
        
        try {
            const token = getAuthToken();
            if (!token) {
                showErrorAlert('请先登录');
                return;
            }
            
            const response = await fetch('/api/delete_master_voice', {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    showSuccessAlert('主人声音频已删除');
                    updateMasterVoiceUI(false);
                } else {
                    showErrorAlert(data.error || '删除失败');
                }
            } else {
                const errorData = await response.json();
                showErrorAlert(errorData.error || '删除请求失败');
            }
        } catch (error) {
            console.error('删除主人声失败:', error);
            showErrorAlert('删除过程中发生错误');
        }
    }

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
            
            // 如果切换到主人声设置标签页，检查状态
            if (tabId === 'master-voice') {
                checkMasterVoiceStatus();
            }
            
            // 如果切换到批量模式标签页，检查并显示主人声状态
            if (tabId === 'batch') {
                checkBatchMasterVoiceStatus();
            }
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

    // 处理文件上传 - 仅批量模式
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

        // 直接使用批量模式处理
        await handleBatchFileUpload(file);
        return;

        // 单文件模式逻辑已移除，现在只支持批量模式
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
    
    // 成功提示函数（别名）
    function showSuccessAlert(message) {
        showSuccessMessage(message);
    }
    
    // 错误提示函数
    function showErrorAlert(message) {
        console.log('showErrorAlert被调用，消息:', message);
        
        const errorAlert = document.createElement('div');
        errorAlert.className = 'error-alert';
        errorAlert.innerHTML = `
            <div class="error-content">
                <span class="error-icon">❌</span>
                <span class="error-text">${message}</span>
                <button class="error-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
        `;
        
        errorAlert.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #f8d7da;
            border: 1px solid #f5c6cb;
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
        
        // 添加错误提示样式（如果还没有的话）
        if (!document.querySelector('#error-alert-styles')) {
            const style = document.createElement('style');
            style.id = 'error-alert-styles';
            style.textContent = `
                .error-content {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    color: #721c24;
                }
                .error-icon {
                    font-size: 18px;
                }
                .error-text {
                    flex: 1;
                    font-weight: 500;
                }
                .error-close {
                    background: none;
                    border: none;
                    font-size: 20px;
                    cursor: pointer;
                    color: #721c24;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .error-close:hover {
                    background: rgba(114, 28, 36, 0.1);
                    border-radius: 50%;
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(errorAlert);
        
        // 5秒后自动移除（错误消息显示时间稍长）
        setTimeout(() => {
            if (errorAlert.parentElement) {
                errorAlert.remove();
            }
        }, 5000);
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
                
                // 不显示具体内容预览，只显示完成状态
                const resultDiv = task.element.querySelector('.task-result');
                const resultPreview = task.element.querySelector('.result-preview');
                if (resultDiv && resultPreview) {
                    resultPreview.textContent = '转录和摘要已完成，结果已保存到飞书多维表格';
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
    
    // 批量模式初始化（现在只有批量模式）
    initBatchMode();
    
    // 批量模式相关函数
    function initBatchMode() {
        const batchProcessBtn = document.getElementById('batch-process-btn');
        const batchClearBtn = document.getElementById('batch-clear-btn');
        
        // 批量处理按钮事件
        if (batchProcessBtn) {
            batchProcessBtn.addEventListener('click', processBatchAudio);
        }
        
        // 清空片段按钮事件
        if (batchClearBtn) {
            batchClearBtn.addEventListener('click', clearBatchSegments);
        }
        
        // 加载批量片段
        loadBatchSegments();
    }
    
    // updateModeUI函数已移除，现在只有批量模式
    
    async function loadBatchSegments() {
        // 现在只有批量模式，移除模式检查
        
        try {
            const token = getAuthToken();
            const response = await fetch('/api/batch_list', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    batchSegments = data.segments || [];
                    updateBatchUI();
                }
            }
        } catch (error) {
            console.error('加载音频片段列表失败:', error);
        }
    }
    
    function updateBatchUI() {
        const batchCount = document.getElementById('batch-count');
        const batchProcessBtn = document.getElementById('batch-process-btn');
        const batchEmptyState = document.getElementById('batch-empty-state');
        const segmentsList = document.getElementById('segments-list');
        
        if (batchCount) {
            batchCount.textContent = batchSegments.length;
        }
        
        if (batchProcessBtn) {
            batchProcessBtn.disabled = batchSegments.length === 0;
        }
        
        if (batchEmptyState) {
            batchEmptyState.style.display = batchSegments.length === 0 ? 'block' : 'none';
        }
        
        if (segmentsList) {
            segmentsList.innerHTML = '';
            batchSegments.forEach(segment => {
                const segmentElement = createSegmentElement(segment);
                segmentsList.appendChild(segmentElement);
            });
        }
    }
    
    function createSegmentElement(segment) {
        const template = document.getElementById('segment-item-template');
        if (!template) return null;
        
        const clone = template.content.cloneNode(true);
        const segmentItem = clone.querySelector('.segment-item');
        
        segmentItem.setAttribute('data-segment-id', segment.segment_id);
        
        const filename = clone.querySelector('.segment-filename');
        const size = clone.querySelector('.segment-size');
        const time = clone.querySelector('.segment-time');
        const removeBtn = clone.querySelector('.segment-remove-btn');
        
        if (filename) filename.textContent = segment.filename;
        if (size) size.textContent = formatFileSize(segment.file_size);
        if (time) time.textContent = formatUploadTime(segment.upload_time);
        
        if (removeBtn) {
            removeBtn.addEventListener('click', () => removeSegment(segment.segment_id));
        }
        
        return clone;
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    function formatUploadTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
        if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
        
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    async function removeSegment(segmentId) {
        // 从本地列表中移除
        batchSegments = batchSegments.filter(s => s.segment_id !== segmentId);
        updateBatchUI();
        
        // 这里可以添加服务器端删除逻辑
        // 目前服务器端会在批量处理或清空时统一清理
    }
    
    async function processBatchAudio() {
        if (batchSegments.length === 0) {
            showErrorAlert('没有待处理的音频片段');
            return;
        }
        
        // 检查主人声状态
        try {
            const token = getAuthToken();
            const masterVoiceResponse = await fetch('/api/check_master_voice', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (masterVoiceResponse.ok) {
                const masterVoiceData = await masterVoiceResponse.json();
                if (!masterVoiceData.has_master_voice) {
                    const userChoice = confirm(
                        '检测到您尚未上传主人声音频。\n\n' +
                        '主人声音频可以帮助系统更准确地识别您的声音，提高转写质量。\n\n' +
                        '点击"确定"继续批量转写（不使用主人声预处理）\n' +
                        '点击"取消"前往设置页面上传主人声音频'
                    );
                    
                    if (!userChoice) {
                        // 用户选择先设置主人声
                        const masterVoiceTab = document.querySelector('[data-tab="master-voice"]');
                        if (masterVoiceTab) {
                            masterVoiceTab.click();
                        }
                        showErrorAlert('请先上传主人声音频以获得更好的转写效果');
                        return;
                    }
                }
            }
        } catch (error) {
            console.warn('检查主人声状态失败，继续批量处理:', error);
        }
        
        const batchProcessBtn = document.getElementById('batch-process-btn');
        if (batchProcessBtn) {
            batchProcessBtn.disabled = true;
            batchProcessBtn.textContent = '正在处理...';
        }
        
        try {
            const token = getAuthToken();
            const response = await fetch('/api/batch_process', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.task_id) {
                    // 异步任务已启动，开始轮询状态
                    showSuccessAlert('批量处理任务已启动，正在后台处理...');
                    await pollTaskStatus(data.task_id, '批量处理');
                } else {
                    showErrorAlert(data.error || '批量处理启动失败');
                }
            } else {
                const errorData = await response.json();
                showErrorAlert(errorData.error || '批量处理请求失败');
            }
        } catch (error) {
            console.error('批量处理失败:', error);
            showErrorAlert('批量处理过程中发生错误');
        } finally {
            if (batchProcessBtn) {
                batchProcessBtn.disabled = batchSegments.length === 0;
                batchProcessBtn.textContent = `统一转写 (${batchSegments.length}个片段)`;
            }
        }
    }
    
    async function clearBatchSegments() {
        if (batchSegments.length === 0) {
            showErrorAlert('没有音频片段需要清空');
            return;
        }
        
        if (!confirm(`确定要清空所有 ${batchSegments.length} 个音频片段吗？`)) {
            return;
        }
        
        try {
            const token = getAuthToken();
            const response = await fetch('/api/batch_clear', {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    showSuccessAlert(`已清空 ${data.cleared_count} 个音频片段`);
                    batchSegments = [];
                    updateBatchUI();
                } else {
                    showErrorAlert(data.error || '清空失败');
                }
            } else {
                const errorData = await response.json();
                showErrorAlert(errorData.error || '清空请求失败');
            }
        } catch (error) {
            console.error('清空音频片段失败:', error);
            showErrorAlert('清空过程中发生错误');
        }
    }
    
    // 批量模式文件上传处理
    async function handleBatchFileUpload(file) {
        try {
            // 验证登录状态
            const token = getAuthToken();
            if (!token) {
                showErrorAlert('请先登录');
                window.location.href = '/login';
                return;
            }
            
            // 检查主人声状态（批量模式）
            try {
                const masterVoiceResponse = await fetch('/api/check_master_voice', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (masterVoiceResponse.ok) {
                const masterVoiceData = await masterVoiceResponse.json();
                if (!masterVoiceData.has_master_voice) {
                    alert(
                        '请先上传主人声音频！\n\n' +
                        '主人声音频是必需的，用于提高语音识别的准确性。\n\n' +
                        '点击确定后将跳转到主人声设置页面。'
                    );
                    
                    // 强制跳转到主人声设置页面
                    const masterVoiceTab = document.querySelector('[data-tab="master-voice"]');
                    if (masterVoiceTab) {
                        masterVoiceTab.click();
                    }
                    return;
                }
            }
            } catch (error) {
                console.error('检查主人声状态失败:', error);
                // 如果检查失败，继续上传流程
            }
            
            // 显示上传进度提示
            showSuccessAlert(`正在上传 ${file.name}...`);
            
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/batch_upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });
            
            if (response.status === 401) {
                showErrorAlert('登录已过期，请重新登录');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                return;
            }
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // 创建片段对象并添加到本地列表
                    const segment = {
                        segment_id: data.segment_id,
                        filename: data.filename,
                        file_size: data.file_size,
                        upload_time: new Date().toISOString()
                    };
                    batchSegments.push(segment);
                    updateBatchUI();
                    showSuccessAlert(`${file.name} 上传成功`);
                } else {
                    showErrorAlert(data.error || '上传失败');
                }
            } else {
                const errorData = await response.json();
                showErrorAlert(errorData.error || '上传请求失败');
            }
        } catch (error) {
            console.error('批量上传失败:', error);
            showErrorAlert('上传过程中发生错误');
        }
    }
    
    // 主人声按钮事件监听器
    const uploadMasterVoiceBtn = document.getElementById('upload-master-voice-btn');
    const deleteMasterVoiceBtn = document.getElementById('delete-master-voice-btn');
    
    if (uploadMasterVoiceBtn) {
        uploadMasterVoiceBtn.addEventListener('click', uploadMasterVoice);
    }
    
    if (deleteMasterVoiceBtn) {
        deleteMasterVoiceBtn.addEventListener('click', deleteMasterVoice);
    }
    
    // 主人声文件输入事件监听器
    const masterVoiceInput = document.getElementById('master-voice-input');
    if (masterVoiceInput) {
        masterVoiceInput.addEventListener('change', handleMasterVoiceFileSelect);
    }
    
    // 页面加载时检查主人声状态
    checkMasterVoiceStatus();
});

// 轮询任务状态
async function pollTaskStatus(taskId, taskName = '任务') {
    const maxAttempts = 120; // 最多轮询2分钟 (120 * 1秒)
    let attempts = 0;
    
    // 创建进度显示元素
    const progressContainer = createProgressDisplay(taskName);
    
    const poll = async () => {
        attempts++;
        
        try {
            const token = getAuthToken();
            const response = await fetch(`/api/task_status/${taskId}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // 更新进度显示
                updateProgressDisplay(progressContainer, data);
                
                if (data.status === 'completed') {
                    // 任务完成
                    removeProgressDisplay(progressContainer);
                    
                    if (data.result && data.result.success) {
                        const result = data.result;
                        if (result.processed_count !== undefined) {
                            // 批量处理完成
                            const modeText = result.has_master_voice ? '（已使用主人声预处理）' : '（标准转写模式）';
                            showSuccessAlert(`${taskName}完成！共处理 ${result.processed_count} 个音频片段 ${modeText}`);
                            batchSegments = [];
                            updateBatchUI();
                            checkBatchMasterVoiceStatus();
                        } else {
                            // 单个音频处理完成
                            showSuccessAlert(`${taskName}完成！`);
                        }
                    } else {
                        showErrorAlert(data.error || `${taskName}失败`);
                    }
                    return;
                } else if (data.status === 'failed') {
                    // 任务失败
                    removeProgressDisplay(progressContainer);
                    showErrorAlert(data.error || `${taskName}失败`);
                    return;
                } else if (data.status === 'running') {
                    // 任务仍在运行，继续轮询
                    if (attempts < maxAttempts) {
                        setTimeout(poll, 1000); // 1秒后再次轮询
                    } else {
                        removeProgressDisplay(progressContainer);
                        showErrorAlert(`${taskName}超时，请稍后查看结果`);
                    }
                }
            } else {
                throw new Error(`查询任务状态失败: ${response.status}`);
            }
        } catch (error) {
            console.error('轮询任务状态失败:', error);
            if (attempts < maxAttempts) {
                setTimeout(poll, 2000); // 出错时2秒后重试
            } else {
                removeProgressDisplay(progressContainer);
                showErrorAlert(`${taskName}状态查询失败`);
            }
        }
    };
    
    // 开始轮询
    poll();
}

// 创建进度显示元素
function createProgressDisplay(taskName) {
    const container = document.createElement('div');
    container.className = 'task-progress-container';
    container.innerHTML = `
        <div class="task-progress-header">
            <span class="task-name">${taskName}进度</span>
            <span class="task-status">准备中...</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
        <div class="task-details"></div>
    `;
    
    // 添加样式
    container.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9998;
        min-width: 300px;
        max-width: 400px;
    `;
    
    // 添加进度条样式
    if (!document.querySelector('#progress-styles')) {
        const style = document.createElement('style');
        style.id = 'progress-styles';
        style.textContent = `
            .task-progress-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                font-weight: 500;
            }
            .task-name {
                color: #333;
            }
            .task-status {
                color: #666;
                font-size: 0.9em;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #f0f0f0;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 10px;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #4CAF50, #45a049);
                transition: width 0.3s ease;
            }
            .task-details {
                font-size: 0.9em;
                color: #666;
                line-height: 1.4;
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(container);
    return container;
}

// 更新进度显示
function updateProgressDisplay(container, taskData) {
    const statusElement = container.querySelector('.task-status');
    const progressFill = container.querySelector('.progress-fill');
    const detailsElement = container.querySelector('.task-details');
    
    // 更新状态
    statusElement.textContent = taskData.status === 'running' ? '处理中...' : taskData.status;
    
    // 更新进度条
    const progress = taskData.progress || 0;
    progressFill.style.width = `${progress}%`;
    
    // 更新详细信息
    if (taskData.current_step) {
        detailsElement.textContent = taskData.current_step;
    }
    
    // 如果有详细信息，显示更多内容
    if (taskData.details) {
        detailsElement.innerHTML = `
            <div>${taskData.current_step || ''}</div>
            <div style="margin-top: 5px; font-size: 0.8em; color: #888;">
                ${taskData.details}
            </div>
        `;
    }
}

// 移除进度显示
function removeProgressDisplay(container) {
    if (container && container.parentNode) {
        container.parentNode.removeChild(container);
    }
}

// 检查批量模式页面的主人声状态
async function checkBatchMasterVoiceStatus() {
    const statusElement = document.getElementById('batch-master-voice-status');
    const textElement = document.getElementById('batch-master-voice-text');
    const linkElement = document.getElementById('batch-master-voice-link');
    
    if (!statusElement || !textElement || !linkElement) {
        return;
    }
    
    try {
        const response = await fetch('/api/check_master_voice', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // 显示状态提示
            statusElement.style.display = 'block';
            
            if (data.has_master_voice) {
                statusElement.className = 'batch-master-voice-status has-master-voice';
                textElement.textContent = '✅ 已设置主人声音频，批量转写将自动进行预处理';
                linkElement.textContent = '查看设置';
            } else {
                statusElement.className = 'batch-master-voice-status no-master-voice';
                textElement.textContent = '⚠️ 未设置主人声音频，建议先上传以获得更好的转写效果';
                linkElement.textContent = '立即设置';
            }
            
            // 设置链接点击事件
            linkElement.onclick = (e) => {
                e.preventDefault();
                // 切换到主人声设置标签页
                const masterVoiceTab = document.querySelector('[data-tab="master-voice"]');
                if (masterVoiceTab) {
                    masterVoiceTab.click();
                }
            };
        } else {
            // 如果请求失败，隐藏状态提示
            statusElement.style.display = 'none';
        }
    } catch (error) {
        console.error('检查主人声状态失败:', error);
        // 发生错误时隐藏状态提示
        statusElement.style.display = 'none';
    }
}