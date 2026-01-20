from modules.AI_api import tts

import unittest
import os
import tempfile

class TestTTSFunction(unittest.TestCase):
    """TTS函数单元测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_text = "这是一个单元测试"
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后的清理工作"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_tts_basic(self):
        """测试基本功能"""
        audio_data = tts(self.test_text, path=self.test_dir)
        
        self.assertIsNotNone(audio_data)
        self.assertGreater(len(audio_data), 0)
    
    def test_tts_different_voices(self):
        """测试不同语音角色"""
        voices = ["narrator", "young_man", "young_woman"]
        
        for voice in voices:
            with self.subTest(voice=voice):
                audio_data = tts(self.test_text, voice_role=voice, path=self.test_dir)
                self.assertGreater(len(audio_data), 0, f"语音角色 {voice} 生成失败")
    
    def test_tts_output_file(self):
        """测试生成的音频文件"""
        output_file = os.path.join(self.test_dir, "test_output.mp3")
        
        # 直接调用函数获取音频数据
        audio_data = tts(self.test_text, path=self.test_dir)
        
        # 手动保存并验证
        with open(output_file, 'wb') as f:
            f.write(audio_data)
        
        self.assertTrue(os.path.exists(output_file))
        self.assertGreater(os.path.getsize(output_file), 0)

# 运行单元测试
if __name__ == '__main__':
    unittest.main()