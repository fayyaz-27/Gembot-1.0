import network
import socket
from machine import Pin, I2S
import time
import urequests
import struct

# Wi-Fi 
SSID = "sonu tannu"
PASSWORD = "A@10101981"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("Connected, IP:", wlan.ifconfig()[0])

connect_wifi()

# Button
button = Pin(4, Pin.IN, Pin.PULL_UP)
debounce_delay = 50  # ms
last_state = 1
last_debounce_time = time.ticks_ms()

# I2S Mic (STT)
# CRITICAL FIX: Increased buffer size for better audio capture
i2s_mic = I2S(
    0,
    sck=Pin(26),
    ws=Pin(25),
    sd=Pin(22),
    mode=I2S.RX,
    bits=16,
    format=I2S.MONO,
    rate=16000,
    ibuf=8192  # Increased from 4096
)

# I2S Speaker (TTS)
i2s_speaker = I2S(
    1,
    sck=Pin(27),
    ws=Pin(14),
    sd=Pin(12),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=44100,
    ibuf=16384
)

# Server Settings
STT_IP = "192.168.1.100"
STT_PORT = 5005
TTS_IP = "192.168.1.100"
TTS_PORT = 5006
END_MARKER = b'END_AUDIO'

# Audio Amplification Settings
GAIN = 100  # Amplify audio by 100x (adjust between 50-200 based on testing)

def amplify_audio(buf, num_bytes):
    """Amplify audio samples to compensate for low INMP441 output"""
    # Convert bytes to int16 array
    samples = struct.unpack(f'<{num_bytes//2}h', buf[:num_bytes])
    
    # Amplify and clip to prevent overflow
    amplified = []
    for sample in samples:
        amp_sample = sample * GAIN
        # Clip to int16 range (-32768 to 32767)
        if amp_sample > 32767:
            amp_sample = 32767
        elif amp_sample < -32768:
            amp_sample = -32768
        amplified.append(int(amp_sample))
    
    # Convert back to bytes
    return struct.pack(f'<{len(amplified)}h', *amplified)

# Gemini API Settings
#GEMINI_API_KEY = "AIzaSyCxgPEjlBXSLKXG9rYT-CnxL8J_CFSEV58"
GEMINI_API_KEY = "AIzaSyCBBVOUfMnNB6KXjI7gtCsRLuH2Qom2PoI"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

SYSTEM_PROMPT = (
    "You are Gemini, I address you as a female, I named you as Gembot from now on, I am Fayyaz. I am an embedded systems developer, "
    "I integrated you with ESP32 and an I2S speaker. Whatever you say, "
    "I can hear in the speaker through a local TTS GTTS module. "
    "I integrated you with: STT OpenAI Whisper local server code running on my laptop's nvidia gpu rtx3050"
    "which is connected with esp32"
    "So I want you to understand that your response should not contain "
    "asterisks or special characters. The response can be short, but if "
    "the question needs explanation, the answer should not exceed 100 words. "
    "if i ask questions in other language, just give answer in that language only, but only use english transliteration"
    "This is a predefined prompt. Now answer this question by the user: "
)

# Main Loop
while True:
    print("\n=== Hold button to record ===")

    # Wait for button press (debounced)
    while True:
        reading = button.value()
        now = time.ticks_ms()
        if reading != last_state:
            last_debounce_time = now
            last_state = reading
        if (time.ticks_diff(now, last_debounce_time) > debounce_delay) and reading == 0:
            break
        time.sleep(0.01)

    print("Recording started...")
    stt_socket = socket.socket()
    try:
        stt_socket.connect((STT_IP, STT_PORT))
    except Exception as e:
        print(f"Failed to connect to STT server: {e}")
        stt_socket.close()
        continue

    buf = bytearray(1024)
    total_bytes = 0
    max_amplitude = 0

    # Record audio while button is pressed
    while True:
        reading = button.value()
        now = time.ticks_ms()
        if reading != last_state:
            last_debounce_time = now
            last_state = reading
        if (time.ticks_diff(now, last_debounce_time) > debounce_delay) and reading == 1:
            break

        num = i2s_mic.readinto(buf)
        if num:
            # CRITICAL FIX: Amplify audio before sending
            amplified_buf = amplify_audio(buf, num)
            stt_socket.sendall(amplified_buf)
            total_bytes += num
            
            # Check amplitude for debugging
            samples = struct.unpack(f'<{num//2}h', buf[:num])
            current_max = max(abs(s) for s in samples)
            if current_max > max_amplitude:
                max_amplitude = current_max

    print(f"Recording finished ({total_bytes} bytes, max amp: {max_amplitude})")
    stt_socket.sendall(END_MARKER)

    # Receive transcription
    try:
        transcription = stt_socket.recv(4096).decode('utf-8').strip()
        print(f"Transcription: {transcription}")
    except Exception as e:
        print(f"Error receiving transcription: {e}")
        transcription = ""
    
    stt_socket.close()

    if not transcription or transcription in ["[Silent audio detected]", "[No speech detected]"]:
        print("No valid transcription, skipping...")
        continue

    # Gemini API Query
    final_prompt = SYSTEM_PROMPT + transcription
    print("Querying Gemini...")
    try:
        response = urequests.post(
            GEMINI_URL, 
            json={"contents":[{"parts":[{"text": final_prompt}]}]},
            headers={"Content-Type":"application/json"},
            timeout=10
        )
        gemini_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        response.close()
        print(f"Gemini: {gemini_text[:100000]}...")
    except Exception as e:
        gemini_text = f"Error contacting Gemini: {e}"
        print(f"{gemini_text}")

    # TTS Playback 
    print("Playing response...")
    tts_socket = socket.socket()
    try:
        tts_socket.connect((TTS_IP, TTS_PORT))
        tts_socket.send(gemini_text.encode('utf-8'))

        partial = b""
        while True:
            chunk = tts_socket.recv(1024)
            if not chunk:
                time.sleep(0.01)
                continue
            partial += chunk
            if END_MARKER in partial:
                chunk_to_play, remainder = partial.split(END_MARKER, 1)
                if chunk_to_play:
                    i2s_speaker.write(chunk_to_play)
                break
            else:
                i2s_speaker.write(chunk)
                partial = b""
    except Exception as e:
        print(f"TTS error: {e}")
    finally:
        tts_socket.close()
    
    print("Done!\n")
