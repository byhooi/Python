"""豆包 TTS 批量语音合成工具。"""

import base64
import binascii
import ctypes
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv
from pydub import AudioSegment


SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

APPID = os.getenv("DOUBAO_APPID", "").strip()
ACCESS_TOKEN = os.getenv("DOUBAO_ACCESS_TOKEN", "").strip()
CLUSTER = os.getenv("DOUBAO_CLUSTER", "volcano_tts").strip()
VOICE_TYPE = os.getenv("DOUBAO_VOICE_TYPE", "BV040_streaming").strip()

SPEED_RATIO = 0.9
VOLUME_RATIO = 1.0
PITCH_RATIO = 1.0

PAUSE_AFTER_UNIT = 1500
PAUSE_BETWEEN_REPEAT = 1000
PAUSE_AFTER_WORD = 1000
PAUSE_BETWEEN_UNITS = 1500

OUTPUT_FILE = "Unit_English_Rhythm.mp3"
API_URL = "https://openspeech.bytedance.com/api/v1/tts"
REQUEST_TIMEOUT = 30

ALL_DATA: Dict[str, List[str]] = {"hello World!": ["hello World!"]}


def show_message(title: str, content: str, error: bool = False) -> None:
    """在 Windows 上弹窗，其余环境输出到终端。"""
    if os.name == "nt":
        icon = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, content, title, icon)
    else:
        print(f"{title}: {content}")


def create_silence(duration_ms: int) -> AudioSegment:
    return AudioSegment.silent(duration=duration_ms)


def validate_config() -> None:
    """启动前检查必要的 API 配置。"""
    missing = []
    if not APPID:
        missing.append("DOUBAO_APPID")
    if not ACCESS_TOKEN:
        missing.append("DOUBAO_ACCESS_TOKEN")
    if missing:
        raise RuntimeError(f".env 缺少配置：{', '.join(missing)}")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("未找到 FFmpeg，请安装并将其加入 PATH")


def text_to_audio(
    text: str, temp_file: Path, session: requests.Session
) -> AudioSegment:
    """调用豆包 TTS API，并返回完整加载到内存的音频片段。"""
    payload = {
        "app": {"appid": APPID, "token": ACCESS_TOKEN, "cluster": CLUSTER},
        "user": {"uid": "python_tts_tool"},
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
            "frontend_type": "unitTson",
        },
    }
    headers = {"Authorization": f"Bearer;{ACCESS_TOKEN}"}

    response = session.post(
        API_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    try:
        response_data = response.json()
    except requests.JSONDecodeError as error:
        raise RuntimeError("TTS API 返回了无效 JSON") from error

    encoded_audio = response_data.get("data")
    if not encoded_audio:
        raise RuntimeError(
            f"TTS API 调用失败：{response_data.get('message', '响应中没有音频数据')}"
        )

    try:
        audio_data = base64.b64decode(encoded_audio, validate=True)
    except (binascii.Error, ValueError) as error:
        raise RuntimeError("TTS API 返回了无效的音频数据") from error

    temp_file.write_bytes(audio_data)
    return AudioSegment.from_file(temp_file, format="mp3")


def build_audio(session: requests.Session, temp_file: Path) -> AudioSegment:
    """根据单词表合成完整音频。"""
    final_audio = AudioSegment.empty()
    for unit_name, words in ALL_DATA.items():
        print(f"  处理: {unit_name}")
        final_audio += text_to_audio(unit_name, temp_file, session)
        final_audio += create_silence(PAUSE_AFTER_UNIT)

        for word in words:
            print(f"    - {word}")
            word_audio = text_to_audio(word, temp_file, session)
            final_audio += word_audio
            final_audio += create_silence(PAUSE_BETWEEN_REPEAT)
            final_audio += word_audio
            final_audio += create_silence(PAUSE_AFTER_WORD)

        final_audio += create_silence(PAUSE_BETWEEN_UNITS)
    return final_audio


def main() -> int:
    output_path = SCRIPT_DIR / OUTPUT_FILE
    print(f"开始生成: {output_path} ...")

    try:
        validate_config()
        with tempfile.TemporaryDirectory() as temp_dir, requests.Session() as session:
            final_audio = build_audio(session, Path(temp_dir) / "speech.mp3")
            final_audio.export(output_path, format="mp3")
    except (OSError, requests.RequestException, RuntimeError) as error:
        show_message("失败", f"生成出错：{error}", error=True)
        return 1

    duration_sec = len(final_audio) / 1000
    show_message(
        "成功", f"音频已生成！\n\n文件: {output_path.name}\n时长: {duration_sec:.1f} 秒"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
