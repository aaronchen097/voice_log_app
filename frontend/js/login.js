// 登录页面JavaScript

class LoginManager {
    constructor() {
        this.loginForm = document.getElementById('login-form');
        this.usernameInput = document.getElementById('username');
        this.passwordInput = document.getElementById('password');
        this.loginBtn = document.getElementById('login-btn');
        this.btnText = this.loginBtn.querySelector('.btn-text');
        this.btnLoading = this.loginBtn.querySelector('.btn-loading');

        this.messageDiv = document.getElementById('login-message');
        
        this.init();
    }
    
    init() {
        // 绑定事件
        this.loginForm.addEventListener('submit', this.handleLogin.bind(this));
        
        // 绑定飞书登录按钮事件（功能已禁用）
        const feishuBtn = document.getElementById('feishu-login-btn');
        if (feishuBtn) {
            feishuBtn.addEventListener('click', this.handleFeishuLogin.bind(this));
        }
        
        // 检查是否已经登录
        this.checkLoginStatus();
        
        // 添加输入框回车事件
        this.usernameInput.addEventListener('keypress', this.handleKeyPress.bind(this));
        this.passwordInput.addEventListener('keypress', this.handleKeyPress.bind(this));
    }
    
    handleKeyPress(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.handleLogin(event);
        }
    }
    
    handleFeishuLogin(event) {
        event.preventDefault();
        this.showMessage('飞书登录功能已被管理员禁用，请使用账号密码登录', 'info');
    }
    
    async handleLogin(event) {
        event.preventDefault();
        
        const username = this.usernameInput.value.trim();
        const password = this.passwordInput.value.trim();
        
        // 验证输入
        if (!username || !password) {
            this.showMessage('请输入账号和密码', 'error');
            return;
        }
        
        // 显示加载状态
        this.setLoading(true);
        this.showMessage('正在验证登录信息...', 'info');
        
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                // 登录成功
                this.showMessage('登录成功，正在跳转...', 'success');
                
                // 使用sessionStorage保存用户信息（仅在当前会话中有效）
                sessionStorage.setItem('user_info', JSON.stringify(result.user));
                sessionStorage.setItem('login_time', new Date().toISOString());
                sessionStorage.setItem('session_active', 'true');
                
                // 立即跳转到主页（不使用延迟）
                window.location.href = '/';
                
                // 注释掉延迟跳转
                // setTimeout(() => {
                //     window.location.href = '/';
                // }, 1500);
                
            } else {
                // 登录失败
                this.showMessage(result.message || '登录失败，请检查账号密码', 'error');
                this.setLoading(false);
            }
            
        } catch (error) {
            console.error('登录请求失败:', error);
            this.showMessage('网络错误，请稍后重试', 'error');
            this.setLoading(false);
        }
    }
    
    setLoading(loading) {
        if (loading) {
            this.loginBtn.disabled = true;
            this.btnText.classList.add('hidden');
            this.btnLoading.classList.remove('hidden');
        } else {
            this.loginBtn.disabled = false;
            this.btnText.classList.remove('hidden');
            this.btnLoading.classList.add('hidden');
        }
    }
    
    showMessage(message, type = 'info') {
        this.messageDiv.textContent = message;
        this.messageDiv.className = `login-message ${type}`;
        this.messageDiv.style.display = 'block';
        
        // 自动隐藏成功和信息消息
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                if (type === 'info') {
                    this.messageDiv.style.display = 'none';
                }
            }, 3000);
        }
    }
    

    
    checkLoginStatus() {
        // 清除任何可能存在的localStorage登录信息
        localStorage.removeItem('user_info');
        localStorage.removeItem('login_time');
        localStorage.removeItem('sessionToken');
        
        // 检查sessionStorage中的会话状态
        const sessionActive = sessionStorage.getItem('session_active');
        const userInfo = sessionStorage.getItem('user_info');
        const loginTime = sessionStorage.getItem('login_time');
        
        if (sessionActive && userInfo && loginTime) {
            // 检查会话是否过期（8小时）
            const loginDate = new Date(loginTime);
            const now = new Date();
            const hoursDiff = (now - loginDate) / (1000 * 60 * 60);
            
            if (hoursDiff < 8) {
                // 会话未过期，显示提示信息但不自动跳转
                this.showMessage('检测到已登录状态，您可以直接访问主页或重新登录', 'info');
                
                // 添加一个"前往主页"的按钮
                const messageDiv = document.getElementById('login-message');
                if (messageDiv) {
                    const goHomeBtn = document.createElement('button');
                    goHomeBtn.textContent = '前往主页';
                    goHomeBtn.className = 'btn-go-home';
                    goHomeBtn.style.cssText = 'margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;';
                    goHomeBtn.onclick = () => {
                        window.location.href = '/';
                    };
                    messageDiv.appendChild(goHomeBtn);
                }
                return;
            } else {
                // 会话已过期，清除sessionStorage
                sessionStorage.removeItem('user_info');
                sessionStorage.removeItem('login_time');
                sessionStorage.removeItem('session_active');
                this.showMessage('登录已过期，请重新登录', 'info');
            }
        }
    }
}

// 工具函数
function clearLoginData() {
    // 清除localStorage中的登录信息
    localStorage.removeItem('user_info');
    localStorage.removeItem('login_time');
    localStorage.removeItem('sessionToken');
    
    // 清除sessionStorage中的会话信息
    sessionStorage.removeItem('user_info');
    sessionStorage.removeItem('login_time');
    sessionStorage.removeItem('session_active');
}

function getUserInfo() {
    const userInfo = sessionStorage.getItem('user_info');
    return userInfo ? JSON.parse(userInfo) : null;
}

function isLoggedIn() {
    const sessionActive = sessionStorage.getItem('session_active');
    const userInfo = sessionStorage.getItem('user_info');
    const loginTime = sessionStorage.getItem('login_time');
    
    if (!sessionActive || !userInfo || !loginTime) {
        return false;
    }
    
    // 检查会话是否过期（8小时）
    const loginDate = new Date(loginTime);
    const now = new Date();
    const hoursDiff = (now - loginDate) / (1000 * 60 * 60);
    
    if (hoursDiff >= 8) {
        clearLoginData();
        return false;
    }
    
    return true;
}

// 登出函数
function logout() {
    clearLoginData();
    window.location.reload(); // 重新加载页面以显示登录表单
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});

// 导出函数供其他页面使用
window.LoginUtils = {
    clearLoginData,
    getUserInfo,
    isLoggedIn
};