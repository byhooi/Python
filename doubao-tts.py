#coding=utf-8
'''
豆包 TTS 批量语音合成工具
基于火山引擎豆包语音合成 API，生成英语单词听力音频

requires Python 3.6 or later
pip install requests pydub python-dotenv
'''
import base64
import json
import uuid
import os
import ctypes
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment

# 加载 .env 配置文件
load_dotenv(Path(__file__).parent / ".env")

# ================= 配置区域 =================
# 火山引擎豆包 TTS 认证信息 (从 .env 文件读取)
APPID = os.getenv("DOUBAO_APPID", "")
ACCESS_TOKEN = os.getenv("DOUBAO_ACCESS_TOKEN", "")
CLUSTER = os.getenv("DOUBAO_CLUSTER", "volcano_tts")
VOICE_TYPE = os.getenv("DOUBAO_VOICE_TYPE", "BV040_streaming")

# 语音参数
SPEED_RATIO = 0.9           # 语速 (0.5-2.0, 1.0为正常)
VOLUME_RATIO = 1.0          # 音量 (0.5-2.0, 1.0为正常)
PITCH_RATIO = 1.0           # 音调 (0.5-2.0, 1.0为正常)

# 停顿时长配置 (毫秒) - 基于儿童英语教学研究
PAUSE_AFTER_UNIT = 1500       # 单元名后停顿
PAUSE_BETWEEN_REPEAT = 1000   # 两遍之间停顿
PAUSE_AFTER_WORD = 1000       # 跟读时间
PAUSE_BETWEEN_UNITS = 1500    # 单元之间停顿

# 输出文件名
OUTPUT_FILE = "Unit_English_Rhythm.mp3"

# 单词表
all_data = {
    "hello World!": ["hello World!"]
}
# ===========================================

# API 配置
HOST = "openspeech.bytedance.com"
API_URL = f"https://{HOST}/api/v1/tts"


def show_msg(title, content):
    """弹窗提示"""
    ctypes.windll.user32.MessageBoxW(0, content, title, 0x40)


def create_silence(duration_ms):
    """生成指定时长的静音片段"""
    return AudioSegment.silent(duration=duration_ms)


def text_to_audio(text, temp_file):
    """
    调用豆包 TTS API 将文本转为音频
    
    Args:
        text: 要合成的文本
        temp_file: 临时文件路径
    
    Returns:
        AudioSegment 对象
    """
    header = {"Authorization": f"Bearer;{ACCESS_TOKEN}"}
    
    request_json = {
        "app": {
            "appid": APPID,
            "token": ACCESS_TOKEN,
            "cluster": CLUSTER
        },
        "user": {
            "uid": "python_tts_tool"
        },
        "audio": {
            "voice_type": VOICE_TYPE,
            "encoding": "mp3",
            "speed_ratio": SPEED_RATIO,
            "volume_ratio": VOLUME_RATIO,
            "pitch_ratio": PITCH_RATIO,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "with_frontend": 1,
            "frontend_type": "unitTson"
        }
    }
    
    resp = requests.post(API_URL, json.dumps(request_json), headers=header)
    resp_json = resp.json()
    
    if "data" not in resp_json:
        error_msg = resp_json.get("message", "未知错误")
        raise Exception(f"TTS API 调用失败: {error_msg}")
    
    # 解码 base64 音频数据并保存
    audio_data = base64.b64decode(resp_json["data"])
    with open(temp_file, "wb") as f:
        f.write(audio_data)
    
    return AudioSegment.from_mp3(temp_file)


def main():
    print(f"开始生成: {OUTPUT_FILE} ...")
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            temp_file = os.path.join(temp_dir, "temp.mp3")
            final_audio = AudioSegment.empty()
            
            for unit_name, words in all_data.items():
                print(f"  处理: {unit_name}")
                
                # 1. 单元名
                unit_audio = text_to_audio(unit_name, temp_file)
                final_audio += unit_audio
                final_audio += create_silence(PAUSE_AFTER_UNIT)
                
                # 2. 每个单词
                for word in words:
                    print(f"    - {word}")
                    
                    # 第一遍
                    word_audio = text_to_audio(word, temp_file)
                    final_audio += word_audio
                    
                    # 两遍之间的停顿
                    final_audio += create_silence(PAUSE_BETWEEN_REPEAT)
                    
                    # 第二遍
                    final_audio += word_audio
                    
                    # 单词结束后的停顿
                    final_audio += create_silence(PAUSE_AFTER_WORD)
                
                # 3. 单元之间的停顿
                final_audio += create_silence(PAUSE_BETWEEN_UNITS)
            
            # 导出
            final_audio.export(output_path, format="mp3")
            
            duration_sec = len(final_audio) / 1000
            show_msg("成功", f"音频已生成！\n\n文件: {OUTPUT_FILE}\n时长: {duration_sec:.1f} 秒")
            
        except Exception as e:
            show_msg("失败", f"生成出错: {str(e)}")


if __name__ == "__main__":
    main()
