document.addEventListener("DOMContentLoaded", () => {
    // 如果当前是登录页面，则不执行后续的认证检查和功能初始化
    if (window.location.pathname === '/login' || window.location.pathname === '/login.html') {
        return;
    }
    // 检查用户登录状态
    if (!checkAuthStatus()) {
        return;
    }

    // 原有元素
    const recordButton = document.getElementById("recordButton");
    const statusDiv = document.getElementById("status");
    const resultDiv = document.getElementById("result");
    const summaryDiv = document.getElementById("summary");
    const queryInput = document.getElementById("queryInput");
    const queryButton = document.getElementById("queryButton");
    const queryResultDiv = document.getElementById("queryResult");

    // 获取认证token
    function getAuthToken() {
        return localStorage.getItem('sessionToken') || '';
    }
    
    // 验证token有效性
    async function validateToken() {
        const token = getAuthToken();
        if (!token) {
            return false;
        }
        
        try {
            const response = await fetch('/api/user/info?session_id=' + encodeURIComponent(token), {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                return true;
            } else if (response.status === 401) {
                // Token已过期或无效，清除本地存储
                console.log('Token已过期，清除会话信息');
                sessionStorage.removeItem('user_info');
                sessionStorage.removeItem('login_time');
                sessionStorage.removeItem('session_active');
                sessionStorage.removeItem('temp_user_info');
                localStorage.removeItem('sessionToken');
                return false;
            }
        } catch (error) {
            console.error('Token验证失败:', error);
            return false;
        }
        
        return false;
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
    const fileInput = document.getElementById("file-input");
    const uploadArea = document.getElementById("upload-area");
    const progressSection = document.getElementById("progress-section");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const statusDetails = document.getElementById("status-details");
    const resultSection = document.getElementById("result-section");
    const summarySection = document.getElementById("summary-section");
    const transcriptionContent = document.getElementById("transcription-content");
    const summaryResult = document.getElementById("summary-result");
    const generateSummaryBtn = document.getElementById("generate-summary-btn");
    const summaryType = document.getElementById("summary-type");
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let currentTranscription = '';

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

    // 处理文件上传
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

        // 显示进度区域
        if (progressSection) {
            progressSection.classList.remove('hidden');
        }
        
        // 隐藏结果区域
        if (resultSection) {
            resultSection.classList.add('hidden');
        }
        if (summarySection) {
            summarySection.classList.add('hidden');
        }

        // 重置进度和计时器
        updateProgress(0, '验证登录状态...', 'upload');
        updateTimer(0);
        
        // 验证token有效性
        const isTokenValid = await validateToken();
        if (!isTokenValid) {
            updateProgress(0, '登录已过期，请重新登录');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            return;
        }
        
        updateProgress(5, '准备上传...', 'upload');
        
        // 开始计时
        const startTime = Date.now();
        let timerInterval;

        try {
            const formData = new FormData();
            formData.append('file', file);

            updateProgress(10, '正在上传文件...', 'upload');
            
            // 启动计时器显示等待时长
            timerInterval = setInterval(() => {
                const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
                updateTimer(elapsedSeconds);
                
                if (statusDetails) {
                    statusDetails.innerHTML = `<span style="color: #10B981; font-weight: 500;">🔄 正在处理音频文件...</span>`;
                }
            }, 1000);

            const response = await fetch('/api/voice_log', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                },
                body: formData
            });

            if (response.status === 401) {
                // 认证失败，跳转到登录页面
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            updateProgress(50, '文件上传完成，正在进行语音识别...', 'process');

            const result = await response.json();
            
            // 清除计时器
            if (timerInterval) {
                clearInterval(timerInterval);
            }
            
            const totalTime = Math.floor((Date.now() - startTime) / 1000);
            const totalMinutes = Math.floor(totalTime / 60);
            const totalSeconds = totalTime % 60;
            const totalTimeStr = totalMinutes > 0 ? `${totalMinutes}分${totalSeconds}秒` : `${totalSeconds}秒`;
            
            updateProgress(100, `✅ 转写完成！总用时: ${totalTimeStr}`, 'complete');
            
            // 最终更新计时器显示
            updateTimer(totalTime);
            
            // 显示上传成功提示
            console.log('准备显示成功提示');
            showSuccessMessage('文件上传成功！语音转录已完成。');
            console.log('成功提示已调用');
            
            // 显示转录结果
            currentTranscription = result.text || '';
            if (transcriptionContent) {
                transcriptionContent.textContent = currentTranscription;
            }
            if (resultSection) {
                resultSection.classList.remove('hidden');
            }

            // 如果有摘要，显示摘要区域
            if (result.summary) {
                if (summaryResult) {
                    summaryResult.innerHTML = `<p>${result.summary}</p>`;
                }
                if (summarySection) {
                    summarySection.classList.remove('hidden');
                }
            } else {
                // 显示摘要生成按钮
                if (summarySection) {
                    summarySection.classList.remove('hidden');
                }
            }

            // 显示最终状态
            if (statusDetails) {
                statusDetails.innerHTML = `<span style="color: #28a745; font-weight: bold;">✅ 处理完成</span>，总用时: ${totalTimeStr}`;
            }

            // 隐藏进度区域
            setTimeout(() => {
                if (progressSection) {
                    progressSection.classList.add('hidden');
                }
            }, 3000);

        } catch (error) {
            // 清除计时器
            if (timerInterval) {
                clearInterval(timerInterval);
            }
            
            console.error('上传失败:', error);
            updateProgress(0, '❌ 处理失败，请重试');
            
            // 重置步骤指示器
            const steps = ['step-upload', 'step-process', 'step-complete'];
            steps.forEach(stepId => {
                const step = document.getElementById(stepId);
                if (step) {
                    step.classList.remove('active', 'completed');
                }
            });
            
            if (statusDetails) {
                statusDetails.innerHTML = `<span style="color: #EF4444; font-weight: 500;">❌ 错误详情: ${error.message}</span>`;
            }
            
            // 3秒后隐藏进度区域
            setTimeout(() => {
                if (progressSection) {
                    progressSection.classList.add('hidden');
                }
            }, 3000);
        }
    }

    // 更新进度显示
    function updateProgress(percent, message, step = null) {
        if (progressFill) {
            progressFill.style.width = `${percent}%`;
        }
        if (progressText) {
            progressText.textContent = message;
        }
        
        // 更新百分比显示
        const progressPercentage = document.getElementById('progress-percentage');
        if (progressPercentage) {
            progressPercentage.textContent = `${percent}%`;
        }
        
        // 更新步骤指示器
        updateProgressSteps(step, percent);
    }
    
    // 更新步骤指示器
    function updateProgressSteps(currentStep, percent) {
        const steps = {
            'upload': document.getElementById('step-upload'),
            'process': document.getElementById('step-process'),
            'complete': document.getElementById('step-complete')
        };
        
        // 重置所有步骤状态
        Object.values(steps).forEach(step => {
            if (step) {
                step.classList.remove('active', 'completed');
            }
        });
        
        // 根据进度设置步骤状态
        if (percent <= 30) {
            // 上传阶段
            if (steps.upload) {
                steps.upload.classList.add('active');
            }
        } else if (percent <= 90) {
            // 处理阶段
            if (steps.upload) {
                steps.upload.classList.add('completed');
            }
            if (steps.process) {
                steps.process.classList.add('active');
            }
        } else {
            // 完成阶段
            if (steps.upload) {
                steps.upload.classList.add('completed');
            }
            if (steps.process) {
                steps.process.classList.add('completed');
            }
            if (steps.complete) {
                steps.complete.classList.add('active');
            }
        }
        
        // 如果指定了特定步骤，覆盖自动判断
        if (currentStep && steps[currentStep]) {
            Object.values(steps).forEach(step => {
                if (step) {
                    step.classList.remove('active');
                }
            });
            steps[currentStep].classList.add('active');
        }
    }
    
    // 更新等待时间显示
    function updateTimer(elapsedSeconds) {
        const timerValue = document.getElementById('timer-value');
        if (timerValue) {
            const minutes = Math.floor(elapsedSeconds / 60);
            const seconds = elapsedSeconds % 60;
            const timeStr = minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`;
            timerValue.textContent = timeStr;
        }
    }

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

    // 生成摘要功能
    if (generateSummaryBtn) {
        generateSummaryBtn.addEventListener('click', async () => {
            if (!currentTranscription) {
                alert('请先上传音频文件进行转录');
                return;
            }

            const summaryTypeValue = summaryType ? summaryType.value : 'day_report';
            
            generateSummaryBtn.disabled = true;
            generateSummaryBtn.textContent = '生成中...';

            try {
                const response = await fetch('/api/summary', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${getAuthToken()}`
                    },
                    body: JSON.stringify({
                        text: currentTranscription,
                        summary_type: summaryTypeValue
                    })
                });

                if (response.status === 401) {
                    // 认证失败，跳转到登录页面
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const result = await response.json();
                
                if (summaryResult) {
                    summaryResult.innerHTML = `<p>${result.summary}</p>`;
                }

            } catch (error) {
                console.error('摘要生成失败:', error);
                if (summaryResult) {
                    summaryResult.innerHTML = `<p style="color: red;">摘要生成失败: ${error.message}</p>`;
                }
            } finally {
                generateSummaryBtn.disabled = false;
                generateSummaryBtn.textContent = '生成摘要';
            }
        });
    }

    // 录音功能
    if (recordButton) {
        recordButton.addEventListener("click", async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                isRecording = true;
                recordButton.textContent = "停止录音";
                recordButton.classList.add("recording");
                if (statusDiv) statusDiv.textContent = "录音中...";
                audioChunks = [];

                mediaRecorder.addEventListener("dataavailable", event => {
                    audioChunks.push(event.data);
                });

                mediaRecorder.addEventListener("stop", async () => {
                    const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
                    await uploadAudio(audioBlob);
                    isRecording = false;
                recordButton.textContent = "开始录音";
                recordButton.classList.remove("recording");
                if (statusDiv) statusDiv.textContent = "录音完成，等待处理结果...";
                });

            } catch (error) {
                console.error("录音失败:", error);
                if (statusDiv) statusDiv.textContent = "错误：无法获取麦克风权限。请检查浏览器设置。";
            }
        } else {
            mediaRecorder.stop();
        }
        });
    }

    // 上传音频文件
    async function uploadAudio(audioBlob) {
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.wav");

        try {
            const response = await fetch("/api/voice_log", {
                method: "POST",
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                },
                body: formData,
            });

            if (response.status === 401) {
                // 认证失败，跳转到登录页面
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (statusDiv) statusDiv.textContent = "处理完成！";
            if (resultDiv) resultDiv.innerHTML = `<strong>识别内容:</strong><p>${data.text}</p>`;
            if (summaryDiv) summaryDiv.innerHTML = `<strong>智能摘要:</strong><p>${data.summary}</p>`;

        } catch (error) {
            console.error("上传失败:", error);
            if (statusDiv) statusDiv.textContent = "错误：上传或处理失败。";
            if (resultDiv) resultDiv.textContent = "";
            if (summaryDiv) summaryDiv.textContent = "";
        }
    }

    // 智能查询功能
    if (queryButton) {
        queryButton.addEventListener("click", async () => {
        const query = queryInput ? queryInput.value : '';
        if (!query) {
            if (queryResultDiv) queryResultDiv.textContent = "请输入查询内容。";
            return;
        }

        try {
            if (queryResultDiv) queryResultDiv.textContent = "查询中...";
            const response = await fetch(`/api/query?query=${encodeURIComponent(query)}`, {
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                }
            });

            if (response.status === 401) {
                // 认证失败，跳转到登录页面
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.answer) {
                if (queryResultDiv) queryResultDiv.innerHTML = `<strong>查询结果:</strong><p>${data.answer}</p>`;
            } else {
                if (queryResultDiv) queryResultDiv.textContent = "未找到相关信息。";
            }

        } catch (error) {
            console.error("查询失败:", error);
            if (queryResultDiv) queryResultDiv.textContent = "错误：查询失败。";
        }
        });
    }
});