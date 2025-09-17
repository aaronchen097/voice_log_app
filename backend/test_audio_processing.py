#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试音频处理功能
"""

import os
import sys
import logging
from utils import (
    get_master_voice_path,
    prepare_audio_with_master_voice,
    concatenate_audio_with_master_voice
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_audio_libraries():
    """测试音频处理库是否可用"""
    ffmpeg_available = False
    pydub_available = False
    
    # 测试 ffmpeg-python
    try:
        import ffmpeg
        logging.info("✓ ffmpeg-python 库导入成功")
        ffmpeg_available = True
    except ImportError as e:
        logging.error(f"✗ ffmpeg-python 库导入失败: {e}")
    
    # 测试 pydub
    try:
        from pydub import AudioSegment
        logging.info("✓ pydub 库导入成功")
        pydub_available = True
    except ImportError as e:
        logging.error(f"✗ pydub 库导入失败: {e}")
    
    if ffmpeg_available or pydub_available:
        logging.info("✓ 至少有一个音频处理库可用")
        return True
    else:
        logging.error("✗ 没有可用的音频处理库")
        return False

def test_master_voice_path():
    """测试主人声路径获取"""
    user_id = "ou_584451803266303057bfe907717c64f6"  # 从目录结构中看到的用户ID
    master_voice_path = get_master_voice_path(user_id)
    
    if master_voice_path:
        logging.info(f"✓ 找到主人声文件: {master_voice_path}")
        if os.path.exists(master_voice_path):
            logging.info(f"✓ 主人声文件存在: {os.path.getsize(master_voice_path)} bytes")
            return master_voice_path
        else:
            logging.error(f"✗ 主人声文件不存在: {master_voice_path}")
    else:
        logging.error(f"✗ 未找到用户 {user_id} 的主人声文件")
    
    return None

def test_audio_concatenation():
    """测试音频拼接功能"""
    user_id = "ou_584451803266303057bfe907717c64f6"
    
    # 检查批量上传目录中是否有音频文件
    batch_dir = f"batch_uploads/{user_id}"
    if not os.path.exists(batch_dir):
        logging.error(f"✗ 批量上传目录不存在: {batch_dir}")
        return False
    
    # 查找音频文件
    audio_files = []
    for file in os.listdir(batch_dir):
        if file.lower().endswith(('.wav', '.mp3', '.m4a', '.flac')):
            audio_files.append(os.path.join(batch_dir, file))
    
    if not audio_files:
        logging.error(f"✗ 在 {batch_dir} 中未找到音频文件")
        return False
    
    test_audio = audio_files[0]
    logging.info(f"✓ 使用测试音频: {test_audio}")
    
    # 测试音频预处理
    processed_path = prepare_audio_with_master_voice(test_audio, user_id)
    
    if processed_path != test_audio:
        logging.info(f"✓ 音频预处理成功: {processed_path}")
        if os.path.exists(processed_path):
            original_size = os.path.getsize(test_audio)
            processed_size = os.path.getsize(processed_path)
            logging.info(f"✓ 原始文件大小: {original_size} bytes")
            logging.info(f"✓ 处理后文件大小: {processed_size} bytes")
            
            if processed_size > original_size:
                logging.info("✓ 处理后文件更大，可能成功添加了主人声")
                return True
            else:
                logging.warning("⚠ 处理后文件没有变大，可能没有成功添加主人声")
        else:
            logging.error(f"✗ 处理后的文件不存在: {processed_path}")
    else:
        logging.error("✗ 音频预处理失败，返回了原始文件路径")
    
    return False

def main():
    """主测试函数"""
    logging.info("开始测试音频处理功能...")
    
    # 测试音频处理库
    if not test_audio_libraries():
        logging.error("音频处理库不可用，请安装: pip install pydub ffmpeg-python")
        return
    
    # 测试主人声路径
    master_voice_path = test_master_voice_path()
    if not master_voice_path:
        logging.error("主人声文件测试失败")
        return
    
    # 测试音频拼接
    if test_audio_concatenation():
        logging.info("✓ 所有测试通过！音频处理功能正常")
    else:
        logging.error("✗ 音频拼接测试失败")

if __name__ == "__main__":
    main()