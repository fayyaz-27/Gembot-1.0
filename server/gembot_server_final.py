#-------------------------------------------------------------------------------
# Name:        gembot_server_final.py
# Purpose:     local server for stt and tts process running on gpu, connected remotely to the esp32
#
# Author:      fayyaz nisar shaikh
#
# Created:     11-03-2026
# Copyright:   (c) fayyaz 2026
#-------------------------------------------------------------------------------

import socket
import torch
import whisper
import numpy as np
import subprocess
from gtts import gTTS
import threading

# ---------------- Settings ----------------
TCP_IP = '0.0.0.0'
STT_PORT = 5005
TTS_PORT = 5006
BUFFER_SIZE = 4096
END_MARKER = b'END_AUDIO'

# ---------------- Load Whisper ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading Whisper on {device}...")

# CRITICAL FIX: Use multilingual model, not .en
model = whisper.load_model("medium.en", device=device)  # or "large" for better accuracy
print("Whisper ready")

# ---------------- STT Handler ----------------
def handle_stt(conn):
    try:
        while True:
            audio_bytes = b""
            while True:
                chunk = conn.recv(BUFFER_SIZE)
                if not chunk:
                    continue
                if END_MARKER in chunk:
                    chunk, _ = chunk.split(END_MARKER, 1)
                    audio_bytes += chunk
                    break
                audio_bytes += chunk

            if not audio_bytes:
                print("⚠️  Received empty audio!")
                continue

            # DIAGNOSTIC INFO
            print(f"📊 Audio received: {len(audio_bytes)} bytes")

            # Convert audio to numpy array
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
            print(f"📊 Samples: {len(audio_np)}, Duration: {len(audio_np)/16000:.2f}s @ 16kHz")
            print(f"📊 Audio range: min={audio_np.min()}, max={audio_np.max()}, mean={audio_np.mean():.1f}")

            # Check if audio is silent or corrupted
            if np.abs(audio_np).max() < 100:
                print("⚠️  Audio seems silent (max amplitude < 100)")
                conn.sendall(b"[Silent audio detected]\n")
                continue

            # Save raw audio for debugging
            import wave
            with wave.open("debug_received.wav", "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                wf.writeframes(audio_bytes)
            print("💾 Saved debug_received.wav for inspection")

            # Normalize audio to [-1, 1] float32
            audio_tensor = torch.from_numpy(audio_np.astype(np.float32) / 32768.0)

            # Whisper expects 16kHz sample rate
            result = model.transcribe(
                audio_tensor,
                fp16=(device == "cuda"),
                language=None,  # Auto-detect
                task="transcribe",
                temperature=0.0,  # More deterministic
                best_of=1,
                beam_size=5
            )

            transcription = result["text"].strip()
            detected_lang = result.get("language", "unknown")

            print(f"🗣️  Detected language: {detected_lang}")
            print(f"📝 Transcription: '{transcription}'")
            print("-" * 60)

            # Send transcription
            if transcription:
                conn.sendall(transcription.encode('utf-8') + b"\n")
            else:
                conn.sendall(b"[No speech detected]\n")

    except Exception as e:
        print(f"❌ STT Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

# ---------------- TTS Handler ----------------
def handle_tts(conn):
    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                continue

            text = data.decode('utf-8').strip()

            # Simple language detection based on Unicode ranges
            # Hindi characters are in range U+0900 to U+097F
            is_hindi = any('\u0900' <= char <= '\u097F' for char in text)
            lang = "hi" if is_hindi else "en"

            print(f"TTS for text: {text[:1000]}... (lang: {lang})")

            # Generate speech
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save("output.mp3")

            # Convert to WAV
            subprocess.run([
                r"D:\ffmpeg\bin\ffmpeg.exe", "-y", "-i", "output.mp3",
                "-ac", "1", "-ar", "44100",
                "-f", "wav", "-acodec", "pcm_s16le", "output.wav"
            ], check=True, capture_output=True)

            # Send WAV data
            with open("output.wav", "rb") as f:
                while True:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    conn.sendall(chunk)

            conn.sendall(END_MARKER)

    except Exception as e:
        print("TTS Error:", e)
    finally:
        conn.close()

# Main Server Loop
def start_server(port, handler):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((TCP_IP, port))
    s.listen(5)
    print(f"Server listening on {TCP_IP}:{port}")

    while True:
        conn, addr = s.accept()
        print(f"Connection from {addr}")
        t = threading.Thread(target=handler, args=(conn,))
        t.daemon = True
        t.start()

# Start both servers in threads
print("Starting STT and TTS servers...")
threading.Thread(target=start_server, args=(STT_PORT, handle_stt), daemon=True).start()
threading.Thread(target=start_server, args=(TTS_PORT, handle_tts), daemon=True).start()

# Keep main thread alive
import time
print("Servers running. Press Ctrl+C to stop.")
while True:
    time.sleep(1)