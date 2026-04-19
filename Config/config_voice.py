from threading import Lock

_voice_lock = Lock()
_engine = None
_voice_available = True


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


def speak(text: str) -> bool:
  if not text:
    return False

  with _voice_lock:
    engine = _get_engine()

    if engine is None:
      return False

    try:
      engine.say(text)
      engine.runAndWait()
      return True
    except Exception:
      return False


def print_and_speak(text: str) -> None:
  print(text)
  speak(text)
