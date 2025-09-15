import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_api import FeishuBitableClient

def test_correct_user_format():
    """使用从用户表获取的正确用户ID格式测试创建记录"""
    try:
        # 获取飞书客户端
        client = FeishuBitableClient()
        
        # 从用户表查询结果中获取的真实用户ID
        # 用户1: ou_60605cb44ad9a136c662dd0b292011f5 (王浩维)
        # 用户2: ou_60605cb44ad9a136c662dd0b2920119f099b05 (张鹏) 
        # 用户3: ou_60605cb44ad9a136c662dd0b292011f5 (王浩维)
        
        test_user_id = "ou_60605cb44ad9a136c662dd0b292011f5"  # 王浩维的ID
        
        print(f"测试用户ID: {test_user_id}")
        print("-" * 50)
        
        # 测试数据 - 只使用实际存在的字段
        # 根据debug_feishu_fields.py的结果，实际存在的字段有：
        # unique_id, 日志内容, 语音转录结果, 个人能力评估, 日期, 人员, 父记录
        test_data = {
            "日志内容": "测试语音日志内容 - 使用正确用户格式",
            "人员": [{
                "id": test_user_id,
                "type": "user"
            }],  # 使用对象格式，包含id和type
            "语音转录结果": "这是测试的语音转录结果",
            "个人能力评估": "技术能力：优秀\n沟通能力：良好\n学习能力：很强"
            # 注意：不包含"日期"字段，让系统自动处理
            # 注意：不包含"语音文件路径"字段，因为表格中不存在此字段
        }
        
        print("测试数据:")
        for key, value in test_data.items():
            print(f"  {key}: {value}")
        print()
        
        # 获取表格ID和应用token
        table_id = os.getenv('FEISHU_LOG_TABLE_ID')
        app_token = os.getenv('FEISHU_LOG_APP_TOKEN')
        
        if not table_id:
            print("❌ 未找到FEISHU_LOG_TABLE_ID环境变量")
            return
            
        if not app_token:
            print("❌ 未找到FEISHU_LOG_APP_TOKEN环境变量")
            return
            
        print(f"表格ID: {table_id}")
        print(f"应用Token: {app_token[:20]}...")
        
        # 尝试创建记录
        print("正在创建记录...")
        result = client.create_records(app_token, table_id, [test_data])
        
        if result:
            print("✅ 成功创建记录！")
            print(f"结果: {result}")
        else:
            print("❌ 创建记录失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_correct_user_format()