# 🤖 GemBot — ESP32 AI Voice Assistant

> An embedded AI voice assistant integrating **ESP32**, **INMP441 Microphone Module**, **MAX98357 Module with Speaker**, **OpenAI Whisper (STT)**, **Google Gemini (LLM)**, and **gTTS (TTS)** over a local TCP server running on an NVIDIA GPU.

---

## 📌 Project Overview

GemBot is a voice-activated AI assistant built on an ESP32 microcontroller. Press and hold the button to speak — your voice is transcribed by a local Whisper server, processed by Gemini AI (On ESP32), and the response is spoken back through an I2S speaker in real time via gTTS (Google TTS running on server)

```
[Button Press] → [I2S Mic] → [ESP32] → [Whisper STT Server (GPU)] → [ESP32] → [Gemini API] → [ESP32] → [gTTS Server] → [ESP32] → [I2S Speaker]
```

---

## 🛠️ Hardware

| Component         | Pin(s)              |
|------------------|---------------------|
| Push Button       | GPIO **4**          |
| I2S Mic (INMP441) | SCK=**26**, WS=**25**, SD=**22** |
| I2S Speaker (MAX98357) | SCK=**27**, WS=**14**, SD=**12** |

---

## 🖥️ Server Setup (PC / GPU Machine)

### Requirements

```bash
pip install torch whisper gtts numpy
```

Also requires **FFmpeg** installed and accessible. Update the path in `gembot_server_final.py`:

```python
r"D:\ffmpeg\bin\ffmpeg.exe"  # Update this to your FFmpeg path
```

### Running the Server

```bash
python gembot_server_final.py
```

This starts two TCP servers:

| Server | Port | Purpose |
|--------|------|---------|
| STT    | `5005` | Receives audio from ESP32, returns transcription |
| TTS    | `5006` | Receives text from ESP32, returns WAV audio |

### Whisper Models Available

```
tiny.en, tiny, base.en, base, small.en, small,
medium.en, medium, large-v1, large-v2, large-v3,
large, large-v3-turbo, turbo
```

> Currently using `medium.en`. Change in the server script as needed for speed/accuracy tradeoff.

---

## 📟 ESP32 Setup (MicroPython)

### Configuration

Update these values in the ESP32 script before flashing:

```python
# Wi-Fi
SSID = "your_wifi_name"
PASSWORD = "your_wifi_password"

# Server IP (your PC's local IP)
STT_IP = "192.168.1.100"
TTS_IP = "192.168.1.100"

# Gemini API Key
GEMINI_API_KEY = "your_gemini_api_key"
```

### Flashing

Use [Thonny IDE](https://thonny.org/) or to upload the MicroPython script to your ESP32.

---

## 🔁 How It Works

1. **Button held** → ESP32 starts recording via I2S mic at **16kHz, 16-bit mono**
2. Audio is **amplified** (default GAIN=100) and streamed to the STT server over TCP by ESP32
3. **Whisper** on the GPU transcribes the audio and returns text to the ESP32
4. The transcription is sent to **Gemini 2.5 Flash** with a system prompt by ESP32
5. Gemini's response is sent back to the ESP32 which then sends it to the other port of **TTS server**
6. **gTTS** converts the text to speech (auto-detects Hindi/English)
7. Audio is streamed back to ESP32 and played via the I2S speaker at **44100Hz**

---

## ⚙️ Audio Settings

| Parameter      | Value     | Notes                              |
|----------------|-----------|------------------------------------|
| Mic Sample Rate | 16000 Hz | Required by Whisper                |
| Mic Bit Depth  | 16-bit    | PCM signed                         |
| Speaker Rate   | 44100 Hz  | Matches gTTS output                |
| Audio Gain     | 100x      | Adjustable (50–200) for INMP441 low output |
| Mic Buffer     | 8192 bytes | Increased for better capture       |
| Speaker Buffer | 16384 bytes | Smooth playback                   |

---

## 🌐 System Prompt (Gemini)

GemBot is configured as a female AI assistant named **Gembot**, with the following behavior:
- Responds without asterisks or special characters
- Keeps answers under ~100 words unless explanation is needed
- Responds in the same language the user speaks (using English transliteration for non-English languages)

---

## 🐛 Debugging

- A `debug_received.wav` file is saved on the server after each STT request — inspect it to verify mic audio quality.
- Server logs print audio byte count, amplitude range, detected language, and transcription for each request.

---

## 👤 Author

**Fayyaz Nisar Shaikh**  
Embedded Systems Developer  
Created: 11-03-2026

---

## 📄 License

© 2026 Fayyaz. All rights reserved.
