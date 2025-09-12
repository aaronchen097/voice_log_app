# 更新日志

## [2025-01-10] - 认证方式统一化优化

### 修复
- **解决音频连续上传问题**: 修复了用户在主页面上传音频后无法连续上传多个音频的问题，现在用户无需重新登录即可连续上传音频文件

### 技术改进
- **统一认证方式**: 将前后端认证方式统一为Bearer token认证
  - 修改后端 `/api/user/info` 接口，使用 `Depends(get_current_user)` 依赖注入替代 `session_id` 查询参数
  - 修改前端 `validateToken()` 函数，移除 `session_id` 查询参数，统一使用 `Authorization` header
- **修复静态文件路径**: 修正了后端静态文件目录路径配置问题

### 影响范围
- 前端: `frontend/js/script.js` - validateToken函数
- 后端: `backend/main.py` - /api/user/info接口和静态文件配置

### 测试验证
- ✅ 用户登录功能正常
- ✅ 首次音频上传功能正常
- ✅ 连续音频上传无需重新登录
- ✅ Token过期时正确跳转到登录页面

### 技术细节
问题根因：前端 `validateToken()` 函数使用 `session_id` 查询参数调用 `/api/user/info` 接口，而音频上传接口使用 Bearer token 认证，两种认证方式不一致导致会话状态管理混乱。

解决方案：统一使用 Bearer token 认证方式，确保所有API接口的认证逻辑一致。