from pathlib import Path
import os
import tempfile
import wave

import numpy as np
import whisper

try:
  import sounddevice as sd
except ImportError:
  sd = None

_model = None
DEFAULT_MIC_DEVICE_NAME = "WO Mic"
MIN_AUDIO_RMS = 0.002
DEFAULT_SILENCE_SECONDS = 1.0
DEFAULT_VOICE_THRESHOLD = 0.008
NOISE_MULTIPLIER = 3.0
PRE_SPEECH_CHUNKS = 3
WHISPER_INITIAL_PROMPT = (
  "Comandos em portugues para o assistente Steel controlar o Spotify. "
  "Palavras comuns: Steel, Estil, Estiu, Spotify, abrir Spotify, fechar Spotify, "
  "tocar musica, pausar musica, proxima musica, musica anterior, aumentar volume, "
  "diminuir volume, tocar Legiao Urbana, tocar Sistema Fandals."
)
DEVICE_HOST_API_PREFERENCE = [
  "Windows WASAPI",
  "Windows DirectSound",
  "MME",
  "Windows WDM-KS",
]


def get_whisper_model():
  global _model
  if _model is None:
    _model = whisper.load_model("small")
  return _model


def transcribe_audio(audio_path: str | Path) -> str:
  audio_path = Path(audio_path)
  if audio_path.suffix.lower() == ".wav":
    return transcribe_audio_data(load_wav_audio(audio_path))

  model = get_whisper_model()
  result = model.transcribe(str(audio_path), language="pt", fp16=False)
  return result["text"].strip()


def transcribe_audio_data(audio: np.ndarray) -> str:
  audio = prepare_audio_for_transcription(audio)
  if audio is None:
    return ""

  model = get_whisper_model()
  result = model.transcribe(
    audio,
    language="pt",
    fp16=False,
    condition_on_previous_text=False,
    initial_prompt=WHISPER_INITIAL_PROMPT,
    temperature=0,
  )
  return clean_transcription(result["text"])


def clean_transcription(text: str) -> str:
  text = text.strip()

  if not text:
    return ""

  if "<|" in text or "|>" in text:
    return ""

  if sum(1 for char in text if ord(char) > 255) > 2:
    return ""

  return " ".join(text.split())


def audio_stats(audio: np.ndarray) -> dict[str, float]:
  if audio.size == 0:
    return {"rms": 0.0, "peak": 0.0}

  return {
    "rms": float(np.sqrt(np.mean(np.square(audio)))),
    "peak": float(np.max(np.abs(audio))),
  }


def prepare_audio_for_transcription(audio: np.ndarray) -> np.ndarray | None:
  stats = audio_stats(audio)

  if stats["rms"] < MIN_AUDIO_RMS:
    return None

  peak = stats["peak"]
  if peak > 0:
    audio = audio / max(peak, 0.05)

  return np.clip(audio, -1, 1).astype(np.float32)


def resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
  if source_rate == target_rate or audio.size == 0:
    return audio.astype(np.float32)

  duration = audio.size / source_rate
  source_times = np.linspace(0, duration, num=audio.size, endpoint=False)
  target_size = int(duration * target_rate)
  target_times = np.linspace(0, duration, num=target_size, endpoint=False)

  return np.interp(target_times, source_times, audio).astype(np.float32)


def get_device_sample_rate(device: int | None, fallback_sample_rate: int) -> int:
  if sd is None:
    return fallback_sample_rate

  try:
    info = sd.query_devices(device, "input")
    return int(info["default_samplerate"])
  except Exception:
    return fallback_sample_rate


def load_wav_audio(audio_path: str | Path) -> np.ndarray:
  with wave.open(str(audio_path), "rb") as file:
    channels = file.getnchannels()
    sample_width = file.getsampwidth()
    frames = file.readframes(file.getnframes())

  if sample_width != 2:
    raise ValueError("Use arquivos WAV com 16 bits para transcrever sem ffmpeg.")

  audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

  if channels > 1:
    audio = audio.reshape(-1, channels).mean(axis=1)

  return audio


def list_audio_input_devices() -> list[str]:
  if sd is None:
    return []

  devices = sd.query_devices()
  host_apis = sd.query_hostapis()
  input_devices = []

  for index, device in enumerate(devices):
    if int(device.get("max_input_channels", 0)) > 0:
      host_api = host_apis[int(device["hostapi"])]["name"]
      input_devices.append(f"{index}: {device['name']} [{host_api}]")

  return input_devices


def resolve_input_device(device_name: str | None = None) -> int | None:
  if sd is None:
    return None

  preferred_device = device_name or os.getenv("MIC_DEVICE_NAME") or DEFAULT_MIC_DEVICE_NAME

  if preferred_device.isdigit():
    return int(preferred_device)

  devices = sd.query_devices()
  host_apis = sd.query_hostapis()
  candidates = []

  for index, device in enumerate(devices):
    name = str(device["name"])
    has_input = int(device.get("max_input_channels", 0)) > 0

    if has_input and preferred_device.lower() in name.lower():
      host_api = host_apis[int(device["hostapi"])]["name"]
      candidates.append((index, host_api))

  if not candidates:
    return None

  for preferred_host_api in DEVICE_HOST_API_PREFERENCE:
    for index, host_api in candidates:
      if preferred_host_api.lower() == host_api.lower():
        return index

  return candidates[0][0]


def record_audio_data(
  duration_seconds: int = 5,
  sample_rate: int = 16000,
  device_name: str | None = None
) -> np.ndarray:
  if sd is None:
    raise RuntimeError(
      "Instale a dependencia sounddevice para usar o microfone: pip install sounddevice"
    )

  device = resolve_input_device(device_name)
  capture_sample_rate = get_device_sample_rate(device, sample_rate)

  recording = sd.rec(
    int(duration_seconds * capture_sample_rate),
    samplerate=capture_sample_rate,
    channels=1,
    dtype="float32",
    device=device,
  )
  sd.wait()

  audio = recording.reshape(-1)
  return resample_audio(audio, capture_sample_rate, sample_rate)


def record_until_silence(
  max_duration_seconds: int = 10,
  silence_seconds: float = DEFAULT_SILENCE_SECONDS,
  sample_rate: int = 16000,
  device_name: str | None = None,
  voice_threshold: float = DEFAULT_VOICE_THRESHOLD,
  chunk_seconds: float = 0.1,
) -> np.ndarray:
  if sd is None:
    raise RuntimeError(
      "Instale a dependencia sounddevice para usar o microfone: pip install sounddevice"
    )

  device = resolve_input_device(device_name)
  capture_sample_rate = get_device_sample_rate(device, sample_rate)
  chunk_size = int(chunk_seconds * capture_sample_rate)
  max_chunks = int(max_duration_seconds / chunk_seconds)
  silence_chunks = max(1, int(silence_seconds / chunk_seconds))
  chunks = []
  pre_speech_chunks = []
  noise_samples = []
  speech_started = False
  silent_chunks_after_speech = 0
  threshold = voice_threshold

  with sd.InputStream(
      samplerate=capture_sample_rate,
      channels=1,
      dtype="float32",
      device=device,
      blocksize=chunk_size,
  ) as stream:
    for chunk_index in range(max_chunks):
      recording, _ = stream.read(chunk_size)
      chunk = recording.reshape(-1)
      chunk_rms = audio_stats(chunk)["rms"]

      if not speech_started and chunk_index < 8:
        noise_samples.append(chunk_rms)
        noise_floor = float(np.median(noise_samples))
        threshold = max(voice_threshold, noise_floor * NOISE_MULTIPLIER)

      is_voice = chunk_rms >= threshold

      if speech_started:
        chunks.append(chunk)

        if is_voice:
          silent_chunks_after_speech = 0
        else:
          silent_chunks_after_speech += 1

        if silent_chunks_after_speech >= silence_chunks:
          break

        continue

      pre_speech_chunks.append(chunk)
      if len(pre_speech_chunks) > PRE_SPEECH_CHUNKS:
        pre_speech_chunks.pop(0)

      if is_voice:
        speech_started = True
        chunks.extend(pre_speech_chunks)
        pre_speech_chunks = []

  if not chunks:
    return np.array([], dtype=np.float32)

  audio = np.concatenate(chunks)
  return resample_audio(audio, capture_sample_rate, sample_rate)


def test_audio_input(duration_seconds: int = 3, device_name: str | None = None) -> str:
  device = resolve_input_device(device_name)
  audio = record_audio_data(
    duration_seconds=duration_seconds,
    device_name=device_name,
  )
  stats = audio_stats(audio)
  status = "ok" if stats["rms"] >= MIN_AUDIO_RMS else "baixo demais"

  return (
    f"device={device} "
    f"rms={stats['rms']:.6f} "
    f"peak={stats['peak']:.6f} "
    f"status={status}"
  )


def record_audio(
  duration_seconds: int = 5,
  sample_rate: int = 16000,
  output_path: str | Path | None = None,
  device_name: str | None = None
) -> Path:
  if output_path is None:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = Path(temp_file.name)
    temp_file.close()
  else:
    output_path = Path(output_path)

  recording = record_audio_data(
    duration_seconds=duration_seconds,
    sample_rate=sample_rate,
    device_name=device_name
  )
  audio = np.int16(np.clip(recording, -1, 1) * 32767)

  with wave.open(str(output_path), "wb") as file:
    file.setnchannels(1)
    file.setsampwidth(2)
    file.setframerate(sample_rate)
    file.writeframes(audio.tobytes())

  return output_path


def listen_and_transcribe(duration_seconds: int = 5, device_name: str | None = None) -> str:
  audio = record_until_silence(
    max_duration_seconds=duration_seconds,
    device_name=device_name,
  )
  return transcribe_audio_data(audio)


if __name__ == "__main__":
  print(transcribe_audio("audio.mp3"))
