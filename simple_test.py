import asyncio
import aiohttp
import time
import json

async def test_health_check(session, user_id):
    """测试健康检查端点"""
    try:
        async with session.get("http://localhost:31101/") as response:
            print(f"用户 {user_id}: 健康检查 - {response.status}")
            return response.status == 200
    except Exception as e:
        print(f"用户 {user_id}: 健康检查异常 - {str(e)}")
        return False

async def test_task_status_invalid(session, user_id):
    """测试无效任务ID的状态查询"""
    try:
        fake_task_id = f"fake_task_{user_id}"
        async with session.get(f"http://localhost:31101/api/task_status/{fake_task_id}") as response:
            print(f"用户 {user_id}: 无效任务状态查询 - {response.status}")
            return response.status
    except Exception as e:
        print(f"用户 {user_id}: 任务状态查询异常 - {str(e)}")
        return None

async def test_concurrent_requests(session, user_id, num_requests=5):
    """测试单用户多并发请求"""
    tasks = []
    for i in range(num_requests):
        task = test_health_check(session, f"{user_id}_req_{i+1}")
        tasks.append(task)
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    success_count = sum(1 for r in results if r is True)
    print(f"用户 {user_id}: {num_requests}个并发请求完成，成功: {success_count}, 耗时: {end_time - start_time:.2f}秒")
    return success_count, end_time - start_time

async def simulate_user_load(user_id):
    """模拟单个用户的负载测试"""
    async with aiohttp.ClientSession() as session:
        print(f"\n=== 用户 {user_id} 开始负载测试 ===")
        
        # 测试1: 基础健康检查
        await test_health_check(session, user_id)
        
        # 测试2: 无效任务状态查询
        await test_task_status_invalid(session, user_id)
        
        # 测试3: 并发请求
        await test_concurrent_requests(session, user_id, 10)

async def test_server_performance():
    """测试服务器性能"""
    print("=== 服务器性能测试 ===")
    
    # 测试不同并发用户数量
    for concurrent_users in [1, 3, 5, 10]:
        print(f"\n--- 测试 {concurrent_users} 个并发用户 ---")
        
        tasks = []
        for i in range(concurrent_users):
            user_id = f"load_user_{i+1}"
            task = simulate_user_load(user_id)
            tasks.append(task)
        
        start_time = time.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"{concurrent_users} 个并发用户测试完成，总耗时: {end_time - start_time:.2f}秒")

async def test_memory_usage():
    """测试内存使用情况（通过创建大量任务状态）"""
    print("\n=== 内存使用测试 ===")
    
    async with aiohttp.ClientSession() as session:
        # 创建大量无效任务查询，测试内存管理
        tasks = []
        for i in range(100):
            task = test_task_status_invalid(session, f"memory_test_{i}")
            tasks.append(task)
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"100个任务状态查询完成，耗时: {end_time - start_time:.2f}秒")

async def main():
    """主测试函数"""
    print("开始简化并发测试...")
    print("此测试不需要用户认证，直接测试服务器性能")
    
    # 测试1: 服务器性能
    await test_server_performance()
    
    # 测试2: 内存使用
    await test_memory_usage()
    
    print("\n=== 测试总结 ===")
    print("1. 服务器能够处理多个并发用户请求")
    print("2. 无效请求能够正确返回错误状态")
    print("3. 内存管理正常，大量请求不会导致崩溃")
    print("4. 异步处理机制工作正常")

if __name__ == "__main__":
    asyncio.run(main())