from pathlib import Path
import tempfile
import wave

import numpy as np
import whisper

try:
  import sounddevice as sd
except ImportError:
  sd = None

_model = None


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
  model = get_whisper_model()
  result = model.transcribe(audio, language="pt", fp16=False)
  return result["text"].strip()


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


def record_audio_data(duration_seconds: int = 5, sample_rate: int = 16000) -> np.ndarray:
  if sd is None:
    raise RuntimeError(
      "Instale a dependencia sounddevice para usar o microfone: pip install sounddevice"
    )

  recording = sd.rec(
    int(duration_seconds * sample_rate),
    samplerate=sample_rate,
    channels=1,
    dtype="float32"
  )
  sd.wait()

  return recording.reshape(-1)


def record_audio(
  duration_seconds: int = 5,
  sample_rate: int = 16000,
  output_path: str | Path | None = None
) -> Path:
  if output_path is None:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = Path(temp_file.name)
    temp_file.close()
  else:
    output_path = Path(output_path)

  recording = record_audio_data(
    duration_seconds=duration_seconds,
    sample_rate=sample_rate
  )
  audio = np.int16(np.clip(recording, -1, 1) * 32767)

  with wave.open(str(output_path), "wb") as file:
    file.setnchannels(1)
    file.setsampwidth(2)
    file.setframerate(sample_rate)
    file.writeframes(audio.tobytes())

  return output_path


def listen_and_transcribe(duration_seconds: int = 5) -> str:
  audio = record_audio_data(duration_seconds=duration_seconds)
  return transcribe_audio_data(audio)


if __name__ == "__main__":
  print(transcribe_audio("audio.mp3"))
