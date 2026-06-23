"""
为 demo/2nf-animation.html 生成各场景旁白 MP3。

Workflow 见：.cursor/skills/explainer-video-html/SKILL.md
Backend 复用：app.infrastructure.tts.narration
  - Python 本地运行
  - 使用 Microsoft 神经网络发音（与 Azure 同名 voice）
  - 无需 Azure Speech Key

可选：azure
  - pip install azure-cognitiveservices-speech
  - 设置环境变量 AZURE_SPEECH_KEY、AZURE_SPEECH_REGION
  - 官方 SDK，本地跑代码，语音合成仍走 Azure 云端

用法：
  pip install edge-tts
  python generate_narration.py
  python generate_narration.py --voice zh-CN-YunxiNeural
  python generate_narration.py --engine azure
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
AUDIO_DIR = DEMO_DIR / "audio"
MANIFEST_PATH = AUDIO_DIR / "manifest.json"

SCENES: list[str] = [
    "今天用 1 分钟讲清楚：什么是第二范式，以及为什么要用它。",
    "假设有这样一张表，记录了学号、姓名、课程和成绩。你觉得这样设计有问题吗？",
    "同一个学号对应同一个姓名，但姓名会在每一行重复出现，这就是冗余。",
    "第二范式要求：所有非主键字段，必须完全依赖于整个主键，而不是只依赖其中一部分。",
    "课程名其实只依赖课程号，并不依赖学号，这就是对部分主键的依赖，违反了第二范式。",
    "正确做法是拆成学生表、课程表和选课表，把部分依赖拆开。",
    "记住：第二范式的核心，就是消除非主键字段对部分主键的依赖。",
]

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


async def synthesize_edge_tts(text: str, out_path: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(out_path))


def synthesize_azure(text: str, out_path: Path, voice: str) -> None:
    import azure.cognitiveservices.speech as speechsdk

    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        raise SystemExit("请设置环境变量 AZURE_SPEECH_KEY 和 AZURE_SPEECH_REGION")

    config = speechsdk.SpeechConfig(subscription=key, region=region)
    config.speech_synthesis_voice_name = voice
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
    )
    config.set_property(speechsdk.PropertyId.SpeechServiceConnection_SynthOutputFormat, "mp3")
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=audio_config)
    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detail = result.cancellation_details.error_details if result.cancellation_details else result.reason
        raise RuntimeError(f"Azure TTS 失败: {detail}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="生成 2NF 讲解动画旁白 MP3")
    parser.add_argument("--engine", choices=("edge", "azure"), default="edge")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []

    print(f"引擎: {args.engine} | 发音人: {args.voice}")
    for i, text in enumerate(SCENES, start=1):
        filename = f"scene-{i:02d}.mp3"
        out_path = AUDIO_DIR / filename
        print(f"[{i}/{len(SCENES)}] 生成 {filename} …")
        if args.engine == "edge":
            await synthesize_edge_tts(text, out_path, args.voice)
        else:
            synthesize_azure(text, out_path, args.voice)
        manifest.append({"scene": i, "file": filename, "text": text})

    meta = {"engine": args.engine, "voice": args.voice, "scenes": manifest}
    MANIFEST_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成。共 {len(SCENES)} 个文件 → {AUDIO_DIR}")
    print("请用本地 HTTP 打开页面：")
    print(f"  cd {DEMO_DIR}")
    print("  python -m http.server 8765")
    print("  浏览器访问 http://localhost:8765/2nf-animation.html")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
