import asyncio
import aiohttp
import time
import json

async def login_user(session, username, password):
    """用户登录获取token"""
    try:
        async with session.post(
            "http://localhost:31101/api/login",
            headers={"Content-Type": "application/json"},
            json={"username": username, "password": password}
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("success"):
                    token = data.get("token")
                    print(f"用户 {username} 登录成功，获取token: {token[:20]}...")
                    return token
                else:
                    print(f"用户 {username} 登录失败: {data.get('message', '未知错误')}")
                    return None
            else:
                error_text = await response.text()
                print(f"用户 {username} 登录请求失败 - {response.status}: {error_text}")
                return None
    except Exception as e:
        print(f"用户 {username} 登录异常 - {str(e)}")
        return None

async def test_concurrent_batch_process(session, user_token, user_id):
    """测试单个用户的批量处理请求"""
    try:
        # 模拟批量处理请求
        async with session.post(
            "http://localhost:31101/api/batch_process",
            headers={
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                task_id = data.get("task_id", "N/A")
                print(f"用户 {user_id}: 批量处理启动成功, task_id: {task_id}")
                return task_id
            else:
                error_text = await response.text()
                print(f"用户 {user_id}: 批量处理失败 - {response.status}: {error_text}")
                return None
    except Exception as e:
        print(f"用户 {user_id}: 请求异常 - {str(e)}")
        return None

async def test_task_status(session, task_id, user_token, user_id):
    """测试任务状态查询"""
    try:
        async with session.get(
            f"http://localhost:31101/api/task_status/{task_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                status = data.get("status", "unknown")
                progress = data.get("progress", 0)
                print(f"用户 {user_id}: 任务状态 - {status}, 进度: {progress}%")
                return data
            else:
                error_text = await response.text()
                print(f"用户 {user_id}: 状态查询失败 - {response.status}: {error_text}")
                return None
    except Exception as e:
        print(f"用户 {user_id}: 状态查询异常 - {str(e)}")
        return None

async def simulate_user(user_id, username, password):
    """模拟单个用户的操作"""
    async with aiohttp.ClientSession() as session:
        print(f"\n=== 用户 {user_id} ({username}) 开始测试 ===")
        
        # 首先登录获取token
        user_token = await login_user(session, username, password)
        
        if not user_token:
            print(f"用户 {user_id}: 无法获取token，跳过测试")
            return
        
        # 启动批量处理任务
        task_id = await test_concurrent_batch_process(session, user_token, user_id)
        
        if task_id:
            # 查询任务状态（多次查询模拟轮询）
            for i in range(3):
                await asyncio.sleep(2)  # 等待2秒
                status_data = await test_task_status(session, task_id, user_token, user_id)
                if status_data and status_data.get("status") in ["completed", "failed"]:
                    break

async def test_api_endpoints(session, user_token, user_id):
    """测试其他API端点的并发性能"""
    endpoints = [
        ("/api/logs", "GET"),
        ("/api/latest_summary", "GET"),
    ]
    
    for endpoint, method in endpoints:
        try:
            if method == "GET":
                async with session.get(
                    f"http://localhost:31101{endpoint}",
                    headers={"Authorization": f"Bearer {user_token}"}
                ) as response:
                    print(f"用户 {user_id}: {endpoint} - {response.status}")
        except Exception as e:
            print(f"用户 {user_id}: {endpoint} 测试异常 - {str(e)}")

async def main():
    """主测试函数"""
    print("开始并发测试...")
    print("注意：此测试需要有效的用户账号，请确保飞书认证配置正确")
    
    # 测试用户列表（需要替换为实际的测试账号）
    test_users = [
        ("test_user_1", "password1"),
        ("test_user_2", "password2"), 
        ("test_user_3", "password3"),
    ]
    
    # 创建多个并发任务
    tasks = []
    for i, (username, password) in enumerate(test_users):
        user_id = f"user_{i+1}"
        task = simulate_user(user_id, username, password)
        tasks.append(task)
    
    # 并发执行所有任务
    start_time = time.time()
    await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    print(f"\n并发测试完成，总耗时: {end_time - start_time:.2f}秒")
    
    # 额外测试：单用户多请求并发
    print("\n=== 单用户多请求并发测试 ===")
    async with aiohttp.ClientSession() as session:
        # 使用第一个用户进行多请求测试
        username, password = test_users[0]
        user_token = await login_user(session, username, password)
        
        if user_token:
            # 并发发送多个API请求
            api_tasks = []
            for i in range(5):
                task = test_api_endpoints(session, user_token, f"concurrent_req_{i+1}")
                api_tasks.append(task)
            
            start_time = time.time()
            await asyncio.gather(*api_tasks, return_exceptions=True)
            end_time = time.time()
            
            print(f"单用户多请求测试完成，耗时: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    asyncio.run(main())
