"""使用 Edge TTS 生成带教学停顿的英语听力音频。"""

import asyncio
import ctypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List

import edge_tts
from pydub import AudioSegment


VOICE_NAME = "en-US-JennyNeural"
RATE = "-10%"

PAUSE_AFTER_UNIT = 1500
PAUSE_BETWEEN_REPEAT = 1000
PAUSE_AFTER_WORD = 1000
PAUSE_BETWEEN_UNITS = 1500

OUTPUT_FILE = "Unit_English_Rhythm.mp3"
SCRIPT_DIR = Path(__file__).resolve().parent

ALL_DATA: Dict[str, List[str]] = {
    "Unit 1": ["rice", "fish ball", "congee", "cake", "bread", "baozi", "dim sum"],
    "Unit 2": ["wash my hands", "brush my teeth", "wash my face"],
    "Unit 3": ["do paper-cutting", "do the lion dance", "kick a shuttlecock"],
    "Unit 4": ["run", "climb", "fly", "walk"],
    "Unit 5": ["helpful", "kind", "warm"],
    "Unit 6": ["farm", "farmer", "sleep", "boy", "wolf"],
    "Daily expressions": ["Me too", "Don't worry", "Here you are", "You're welcome"],
}


def show_message(title: str, content: str, error: bool = False) -> None:
    """在 Windows 上弹窗，其余环境输出到终端。"""
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, content, title, 0x10 if error else 0x40)
    else:
        print(f"{title}: {content}")


async def text_to_audio(text: str, temp_file: Path) -> AudioSegment:
    """将文本合成为 MP3，并返回已加载的音频片段。"""
    communicate = edge_tts.Communicate(text, VOICE_NAME, rate=RATE)
    await communicate.save(str(temp_file))
    return AudioSegment.from_file(temp_file, format="mp3")


async def build_audio(temp_file: Path) -> AudioSegment:
    final_audio = AudioSegment.empty()
    for unit_name, words in ALL_DATA.items():
        print(f"  处理: {unit_name}")
        final_audio += await text_to_audio(unit_name, temp_file)
        final_audio += AudioSegment.silent(duration=PAUSE_AFTER_UNIT)

        for word in words:
            print(f"    - {word}")
            word_audio = await text_to_audio(word, temp_file)
            final_audio += word_audio
            final_audio += AudioSegment.silent(duration=PAUSE_BETWEEN_REPEAT)
            final_audio += word_audio
            final_audio += AudioSegment.silent(duration=PAUSE_AFTER_WORD)

        final_audio += AudioSegment.silent(duration=PAUSE_BETWEEN_UNITS)
    return final_audio


async def main() -> int:
    output_path = SCRIPT_DIR / OUTPUT_FILE
    print(f"开始生成: {output_path} ...")

    try:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("未找到 FFmpeg，请安装并将其加入 PATH")
        with tempfile.TemporaryDirectory() as temp_dir:
            final_audio = await build_audio(Path(temp_dir) / "speech.mp3")
            final_audio.export(output_path, format="mp3")
    except (OSError, RuntimeError, ValueError) as error:
        show_message("失败", f"生成出错：{error}", error=True)
        return 1
    except Exception as error:
        # edge-tts 的网络异常类型随底层 aiohttp 版本变化，统一在入口处理。
        show_message("失败", f"语音服务调用失败：{error}", error=True)
        return 1

    duration_sec = len(final_audio) / 1000
    show_message(
        "成功", f"音频已生成！\n\n文件: {output_path.name}\n时长: {duration_sec:.1f} 秒"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
