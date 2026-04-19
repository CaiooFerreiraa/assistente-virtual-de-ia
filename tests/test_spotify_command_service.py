import unittest
from unittest.mock import patch

from Application import spotify_command_service


class SpotifyCommandServiceTest(unittest.TestCase):
  @patch("Application.spotify_command_service.dar_play", return_value="Dando play no Spotify.")
  def test_retoma_musica_routes_to_dar_play(self, dar_play):
    self.assertEqual(
      spotify_command_service.execute_spotify_command("Retoma musica"),
      "Dando play no Spotify.",
    )
    dar_play.assert_called_once()

  @patch("Application.spotify_command_service.tocar_playlist_a_partir_de_musica", return_value="TOCOU")
  def test_playlist_with_initial_track_routes_to_offset_playback(self, tocar_playlist_a_partir):
    self.assertEqual(
      spotify_command_service.execute_spotify_command(
        "Steel dentro da playlist Best Music, começa pela música de barões da fizer"
      ),
      "TOCOU",
    )
    tocar_playlist_a_partir.assert_called_once_with("best music", "baroes da fizer")


if __name__ == "__main__":
  unittest.main()
