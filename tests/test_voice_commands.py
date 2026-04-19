import unittest

from Domain.voice_commands import (
  clean_playlist_query,
  extract_message_after_wake_word,
  extract_playlist_track_request,
)


class VoiceCommandsTest(unittest.TestCase):
  def test_extract_message_after_wake_word(self):
    self.assertEqual(
      extract_message_after_wake_word("Oi Steel, pausa musica", ["Steel"]),
      "pausa musica",
    )

  def test_clean_playlist_query_removes_wake_word(self):
    self.assertEqual(
      clean_playlist_query("Steel toca a minha playlist Best Musics"),
      "Best Musics",
    )

  def test_extract_playlist_track_request(self):
    self.assertEqual(
      extract_playlist_track_request("Steel dentro da playlist Best Music, começa pela música de barões da fizer"),
      ("best music", "baroes da fizer"),
    )


if __name__ == "__main__":
  unittest.main()
