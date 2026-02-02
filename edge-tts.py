import asyncio
import edge_tts
import ctypes
import os
import tempfile
from pydub import AudioSegment

# ================= 配置区域 =================
# 声音角色
VOICE_NAME = "en-US-JennyNeural"
RATE = "-10%"  # 语速减慢 10%

# 停顿时长配置 (毫秒) - 基于儿童英语教学研究
PAUSE_AFTER_UNIT = 1500       # 单元名后 2秒
PAUSE_BETWEEN_REPEAT = 1000   # 两遍之间 1.5秒
PAUSE_AFTER_WORD = 1000       # 跟读时间 5秒
PAUSE_BETWEEN_UNITS = 1500   # 单元之间 3秒

# 输出文件名
OUTPUT_FILE = "Unit_English_Rhythm.mp3"

# 单词表
all_data = {
    "Unit 1": ["rice", "fish ball", "congee", "cake", "bread", "baozi", "dim sum"],
    "Unit 2": ["wash my hands", "brush my teeth", "wash my face"],
    "Unit 3": ["do paper-cutting", "do the lion dance", "kick a shuttlecock"],
    "Unit 4": ["run", "climb", "fly", "walk"],
    "Unit 5": ["helpful", "kind", "warm"],
    "Unit 6": ["farm", "farmer", "sleep", "boy", "wolf"],
    "Daily expressions": ["Me too","Don't worry","Here you are","You're welcome"]
}
# ===========================================

def show_msg(title, content):
    """弹窗提示"""
    ctypes.windll.user32.MessageBoxW(0, content, title, 0x40)

def create_silence(duration_ms):
    """生成指定时长的静音片段"""
    return AudioSegment.silent(duration=duration_ms)

async def text_to_audio(text, temp_file):
    """将文本转为音频片段"""
    communicate = edge_tts.Communicate(text, VOICE_NAME, rate=RATE)
    await communicate.save(temp_file)
    return AudioSegment.from_mp3(temp_file)

async def main():
    print(f"开始生成: {OUTPUT_FILE} ...")
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            temp_file = os.path.join(temp_dir, "temp.mp3")
            final_audio = AudioSegment.empty()
            
            for unit_name, words in all_data.items():
                print(f"  处理: {unit_name}")
                
                # 1. 单元名
                unit_audio = await text_to_audio(unit_name, temp_file)
                final_audio += unit_audio
                final_audio += create_silence(PAUSE_AFTER_UNIT)
                
                # 2. 每个单词
                for word in words:
                    # 第一遍
                    word_audio = await text_to_audio(word, temp_file)
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
    asyncio.run(main())