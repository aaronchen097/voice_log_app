# 飞书Access Token配置指南

## 问题说明

当前系统的账号密码登录功能依赖飞书多维表格存储用户信息，需要有效的`tenant_access_token`才能正常工作。

## 解决方案

### 方法1：使用提供的脚本获取Token（推荐）

1. **获取App ID和App Secret**
   - 登录飞书开发者后台：https://open.feishu.cn/
   - 选择你的应用
   - 在"基础信息 > 凭证与基础信息"页面获取：
     - `App ID`（格式：cli_xxxxxxxxx）
     - `App Secret`

2. **运行获取Token脚本**
   ```bash
   python get_token.py <你的App_ID> <你的App_Secret>
   ```
   
   示例：
   ```bash
   python get_token.py cli_a1b2c3d4e5f6 your_app_secret_here
   ```

3. **更新.env文件**
   - 将脚本输出的token复制到`.env`文件中：
   ```
   FEISHU_ACCESS_TOKEN=t-g204f6c6XXXXXXXXXXXXXXXXXXXXXXXXX
   ```

4. **重启服务器**
   ```bash
   python main.py
   ```

### 方法2：手动API调用获取Token

如果脚本无法使用，可以手动调用API：

```bash
curl -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "你的App_ID",
    "app_secret": "你的App_Secret"
  }'
```

## Token特性说明

- **有效期**：2小时
- **类型**：tenant_access_token（以`t-`开头）
- **用途**：访问飞书多维表格进行用户认证
- **刷新**：Token过期后需要重新获取

## 常见错误码

- `99991663`：Token无效
- `99991664`：Token过期
- `10014`：App ID或App Secret错误

## 注意事项

1. **安全性**：请妥善保管App Secret，不要提交到版本控制系统
2. **权限**：确保应用有访问多维表格的权限
3. **网络**：确保服务器能访问飞书API（https://open.feishu.cn）
4. **缓存**：如果前端仍显示飞书登录按钮，请清除浏览器缓存

## 测试登录

配置完成后，访问 http://localhost:8000 测试账号密码登录功能。

---

**如有问题，请检查：**
1. App ID和App Secret是否正确
2. Token是否已过期（2小时有效期）
3. 网络连接是否正常
4. 多维表格权限是否配置正确