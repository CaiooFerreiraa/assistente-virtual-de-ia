import types
import unittest
from unittest.mock import patch

from Config import config_voice


class FakeEngine:
  def __init__(self, fail=False):
    self.fail = fail
    self.properties = {}
    self.spoken = []

  def setProperty(self, name, value):
    self.properties[name] = value

  def say(self, text):
    self.spoken.append(text)

  def runAndWait(self):
    if self.fail:
      raise RuntimeError("voice engine failed")


class ConfigVoiceTest(unittest.TestCase):
  def setUp(self):
    config_voice._engine = None
    config_voice._voice_available = True
    config_voice._platform_voice_available = True

  def tearDown(self):
    config_voice._engine = None
    config_voice._voice_available = True
    config_voice._platform_voice_available = True

  def test_speak_uses_pyttsx3_when_available(self):
    engine = FakeEngine()
    fake_pyttsx3 = types.SimpleNamespace(init=lambda: engine)

    with patch.dict("sys.modules", {"pyttsx3": fake_pyttsx3}):
      with patch.object(config_voice, "_speak_with_platform_voice") as platform_voice:
        self.assertTrue(config_voice.speak("oi"))

    self.assertEqual(engine.spoken, ["oi"])
    self.assertEqual(engine.properties["rate"], 180)
    self.assertEqual(engine.properties["volume"], 1.0)
    platform_voice.assert_not_called()

  def test_speak_falls_back_when_pyttsx3_engine_fails(self):
    engine = FakeEngine(fail=True)
    fake_pyttsx3 = types.SimpleNamespace(init=lambda: engine)

    with patch.dict("sys.modules", {"pyttsx3": fake_pyttsx3}):
      with patch.object(config_voice, "_speak_with_platform_voice", return_value=True) as platform_voice:
        self.assertTrue(config_voice.speak("resposta"))

    self.assertFalse(config_voice._voice_available)
    self.assertIsNone(config_voice._engine)
    platform_voice.assert_called_once_with("resposta")

  def test_speak_falls_back_when_pyttsx3_is_disabled(self):
    config_voice._voice_available = False

    with patch.object(config_voice, "_speak_with_platform_voice", return_value=True) as platform_voice:
      self.assertTrue(config_voice.speak("resposta"))

    platform_voice.assert_called_once_with("resposta")

  def test_windows_sapi_fallback_passes_text_as_argument(self):
    with patch.object(config_voice.os, "name", "nt"):
      with patch.object(config_voice.shutil, "which", return_value="powershell"):
        with patch.object(config_voice.subprocess, "run") as run:
          self.assertTrue(config_voice._speak_with_platform_voice("texto seguro"))

    command = run.call_args.args[0]
    self.assertEqual(command[0], "powershell")
    self.assertEqual(command[-1], "texto seguro")

  def test_platform_fallback_disables_itself_after_failure(self):
    with patch.object(config_voice.os, "name", "posix"):
      self.assertFalse(config_voice._speak_with_platform_voice("oi"))

    self.assertFalse(config_voice._platform_voice_available)


if __name__ == "__main__":
  unittest.main()
