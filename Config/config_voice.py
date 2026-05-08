from threading import Lock
import os
import shutil
import subprocess

_voice_lock = Lock()
_engine = None
_voice_available = True
_platform_voice_available = True


def _get_engine():
  global _engine
  global _voice_available

  if not _voice_available:
    return None

  if _engine is not None:
    return _engine

  try:
    import pyttsx3
  except ImportError:
    _voice_available = False
    return None

  try:
    _engine = pyttsx3.init()
    _engine.setProperty("rate", 180)
    _engine.setProperty("volume", 1.0)
    return _engine
  except Exception:
    _voice_available = False
    return None


def _disable_pyttsx3_voice():
  global _engine
  global _voice_available

  _engine = None
  _voice_available = False


def _speech_timeout(text: str) -> int:
  return max(10, min(60, 10 + len(text) // 12))


def _speak_with_windows_sapi(text: str) -> bool:
  command = shutil.which("powershell") or shutil.which("pwsh")
  if command is None:
    return False

  script = (
    "$ErrorActionPreference = 'Stop'; "
    "$speaker = New-Object -ComObject SAPI.SpVoice; "
    "$speaker.Rate = 0; "
    "$speaker.Volume = 100; "
    "$speaker.Speak($args[0]) | Out-Null"
  )
  creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

  try:
    subprocess.run(
      [command, "-NoProfile", "-Command", script, text],
      check=True,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      timeout=_speech_timeout(text),
      creationflags=creation_flags,
    )
    return True
  except Exception:
    return False


def _speak_with_platform_voice(text: str) -> bool:
  global _platform_voice_available

  if not _platform_voice_available:
    return False

  if os.name == "nt" and _speak_with_windows_sapi(text):
    return True

  _platform_voice_available = False
  return False


def speak(text: str) -> bool:
  if not text:
    return False

  with _voice_lock:
    engine = _get_engine()

    if engine is None:
      return _speak_with_platform_voice(text)

    try:
      engine.say(text)
      engine.runAndWait()
      return True
    except Exception:
      _disable_pyttsx3_voice()
      return _speak_with_platform_voice(text)


def print_and_speak(text: str) -> None:
  print(text)
  speak(text)
