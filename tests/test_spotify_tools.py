import unittest
from unittest.mock import Mock, patch

from Tools import spotify


class SpotifyToolsTest(unittest.TestCase):
  def setUp(self):
    spotify._client_credentials_token.clear()
    spotify._user_token.clear()

  @patch("Tools.spotify.platform.system", return_value="Windows")
  @patch("Tools.spotify._windows_process_ids", return_value=set())
  @patch("Tools.spotify.os.startfile")
  def test_abrir_spotify_windows(self, startfile, *_):
    self.assertEqual(spotify.abrir_spotify(), "Spotify aberto.")
    startfile.assert_called_once_with("spotify:")

  @patch("Tools.spotify.platform.system", return_value="Windows")
  @patch("Tools.spotify._bring_windows_process_to_front", return_value=True)
  @patch("Tools.spotify._windows_process_ids", return_value={123})
  @patch("Tools.spotify.os.startfile")
  def test_abrir_spotify_windows_focuses_existing_window(self, startfile, *_):
    self.assertEqual(spotify.abrir_spotify(), "Spotify em primeiro plano.")
    startfile.assert_not_called()

  @patch("Tools.spotify.platform.system", return_value="Linux")
  @patch("Tools.spotify.webbrowser.open")
  def test_abrir_spotify_non_windows(self, browser_open, _):
    self.assertEqual(spotify.abrir_spotify(), "Spotify aberto.")
    browser_open.assert_called_once_with("spotify:")

  @patch("Tools.spotify.platform.system", return_value="Windows")
  @patch("Tools.spotify.subprocess.run")
  def test_fechar_spotify_windows_success(self, run, _):
    run.return_value = Mock(returncode=0)
    self.assertEqual(spotify.fechar_spotify(), "Spotify fechado.")

  @patch("Tools.spotify.platform.system", return_value="Windows")
  @patch("Tools.spotify.subprocess.run")
  def test_fechar_spotify_windows_not_open(self, run, _):
    run.return_value = Mock(returncode=1)
    self.assertEqual(spotify.fechar_spotify(), "Spotify nao estava aberto.")

  @patch("Tools.spotify._spotify_get")
  def test_buscar_musica_formats_tracks(self, spotify_get):
    spotify_get.return_value = {
      "tracks": {
        "items": [
          {
            "name": "Tempo Perdido",
            "uri": "spotify:track:1",
            "artists": [{"name": "Legião Urbana"}],
          }
        ]
      }
    }

    result = spotify.buscar_musica("Tempo Perdido")

    self.assertIn("Tempo Perdido - Legião Urbana", result)
    self.assertIn("spotify:track:1", result)

  @patch("Tools.spotify._spotify_get")
  def test_buscar_musica_handles_empty_result(self, spotify_get):
    spotify_get.return_value = {"tracks": {"items": []}}
    self.assertEqual(spotify.buscar_musica("nada"), "Nenhuma musica encontrada.")

  @patch("Tools.spotify._spotify_get")
  def test_buscar_playlist_formats_playlists(self, spotify_get):
    spotify_get.return_value = {
      "playlists": {
        "items": [
          {
            "name": "Rock BR",
            "uri": "spotify:playlist:1",
            "owner": {"display_name": "User"},
          }
        ]
      }
    }

    result = spotify.buscar_playlist("Rock BR")

    self.assertIn("Rock BR - User", result)
    self.assertIn("spotify:playlist:1", result)

  @patch("Tools.spotify._spotify_get")
  def test_buscar_playlist_handles_empty_result(self, spotify_get):
    spotify_get.return_value = {"playlists": {"items": []}}
    self.assertEqual(spotify.buscar_playlist("nada"), "Nenhuma playlist encontrada.")

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_dispositivos(self, user_request):
    user_request.return_value = {
      "devices": [
        {"name": "PC", "type": "Computer", "is_active": True},
        {"name": "Celular", "type": "Smartphone", "is_active": False},
      ]
    }

    result = spotify.listar_dispositivos()

    self.assertIn("PC (Computer, ativo)", result)
    self.assertIn("Celular (Smartphone, inativo)", result)

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_dispositivos_empty(self, user_request):
    user_request.return_value = {"devices": []}
    self.assertEqual(
      spotify.listar_dispositivos(),
      "Nenhum dispositivo ativo encontrado no Spotify.",
    )

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_minhas_playlists(self, user_request):
    user_request.return_value = {
      "items": [
        {
          "name": "Minha Playlist",
          "uri": "spotify:playlist:1",
          "owner": {"display_name": "Eu"},
          "tracks": {"total": 12},
        }
      ]
    }

    result = spotify.listar_minhas_playlists()

    self.assertEqual(result, "Minha Playlist")

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_minhas_playlists_detalhado(self, user_request):
    user_request.return_value = {
      "items": [
        {
          "name": "Minha Playlist",
          "uri": "spotify:playlist:1",
          "owner": {"display_name": "Eu"},
          "tracks": {"total": 12},
        }
      ]
    }

    result = spotify.listar_minhas_playlists(detalhado=True)

    self.assertIn("Minha Playlist - Eu (12 musicas)", result)
    self.assertIn("spotify:playlist:1", result)

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_musicas_curtidas(self, user_request):
    user_request.return_value = {
      "items": [
        {
          "track": {
            "name": "Song",
            "uri": "spotify:track:1",
            "artists": [{"name": "Artist"}],
          }
        }
      ]
    }

    result = spotify.listar_musicas_curtidas()

    self.assertIn("Song - Artist", result)
    self.assertIn("spotify:track:1", result)

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_artistas_seguidos(self, user_request):
    user_request.return_value = {
      "artists": {
        "items": [
          {"name": "Artist", "uri": "spotify:artist:1"},
        ]
      }
    }

    self.assertEqual(
      spotify.listar_artistas_seguidos(),
      "Artist | uri: spotify:artist:1",
    )

  @patch("Tools.spotify._spotify_user_request")
  def test_listar_meus_artistas(self, user_request):
    user_request.return_value = {
      "items": [
        {"name": "Top Artist", "uri": "spotify:artist:1"},
      ]
    }

    self.assertEqual(
      spotify.listar_meus_artistas(),
      "Top Artist | uri: spotify:artist:1",
    )

  @patch("Tools.spotify._spotify_user_request")
  def test_ensure_spotify_device_uses_active_device(self, user_request):
    user_request.return_value = {
      "devices": [{"id": "device-1", "name": "PC", "is_active": True}]
    }

    self.assertEqual(spotify._ensure_spotify_device(), "device-1")

  @patch("Tools.spotify._spotify_user_request")
  def test_ensure_spotify_device_activates_first_device(self, user_request):
    user_request.side_effect = [
      {"devices": [{"id": "device-1", "name": "PC", "is_active": False}]},
      {},
    ]

    self.assertEqual(spotify._ensure_spotify_device(), "device-1")
    self.assertEqual(user_request.call_args_list[1].args[0], "/me/player")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._current_player", return_value={"is_playing": False, "item": {"name": "Song"}})
  def test_dar_play(self, _, user_request):
    with patch("Tools.spotify._require_spotify_device", return_value="device-1"):
      self.assertEqual(spotify.dar_play(), "Dando play no Spotify.")

    user_request.assert_called_once_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
    )

  @patch("Tools.spotify.abrir_spotify", return_value="Spotify aberto.")
  @patch("Tools.spotify._current_player", return_value={})
  def test_dar_play_without_player_opens_spotify(self, _, abrir):
    self.assertEqual(
      spotify.dar_play(),
      "Spotify aberto. Escolha uma musica ou playlist para eu conseguir retomar.",
    )
    abrir.assert_called_once()

  @patch("Tools.spotify._spotify_user_request", side_effect=RuntimeError("o Spotify recusou esse comando"))
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._current_player", return_value={"is_playing": False, "item": {"name": "Song"}})
  def test_dar_play_handles_spotify_restriction(self, *_):
    self.assertEqual(
      spotify.dar_play(),
      "Nao consegui retomar pelo controle remoto do Spotify. Abra uma musica no app e tente de novo.",
    )

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._spotify_get")
  def test_tocar_musica(self, spotify_get, _, user_request):
    spotify_get.return_value = {
      "tracks": {
        "items": [
          {
            "name": "Song",
            "uri": "spotify:track:1",
            "artists": [{"name": "Artist"}],
          }
        ]
      }
    }

    result = spotify.tocar_musica("Song")

    self.assertEqual(result, "Tocando Song - Artist.")
    user_request.assert_called_once_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={"uris": ["spotify:track:1"]},
    )

  @patch("Tools.spotify._spotify_get")
  def test_tocar_musica_empty_result(self, spotify_get):
    spotify_get.return_value = {"tracks": {"items": []}}
    self.assertEqual(spotify.tocar_musica("nada"), "Nenhuma musica encontrada.")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._spotify_get")
  def test_tocar_playlist(self, spotify_get, _, user_request):
    user_request.side_effect = [
      {"items": []},
      {},
    ]
    spotify_get.return_value = {
      "playlists": {
        "items": [
          {
            "name": "Rock BR",
            "uri": "spotify:playlist:1",
          }
        ]
      }
    }

    result = spotify.tocar_playlist("Rock BR")

    self.assertEqual(result, "Tocando playlist Rock BR.")
    self.assertEqual(user_request.call_args_list[-1].args[0], "/me/player/play")
    user_request.assert_called_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={"context_uri": "spotify:playlist:1"},
    )

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._spotify_get")
  def test_tocar_playlist_prefers_user_playlist(self, spotify_get, _, user_request):
    user_request.side_effect = [
      {
        "items": [
          {
            "name": "Best Music",
            "uri": "spotify:playlist:user",
          }
        ]
      },
      {},
    ]

    result = spotify.tocar_playlist("Best Music")

    self.assertEqual(result, "Tocando sua playlist Best Music.")
    spotify_get.assert_not_called()
    user_request.assert_called_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={"context_uri": "spotify:playlist:user"},
    )

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._spotify_get")
  def test_tocar_playlist_matches_user_playlist_with_transcription_variation(self, spotify_get, _, user_request):
    user_request.side_effect = [
      {
        "items": [
          {
            "name": "Beast Music's",
            "uri": "spotify:playlist:user",
          }
        ]
      },
      {},
    ]

    result = spotify.tocar_playlist("Best Musics")

    self.assertEqual(result, "Tocando sua playlist Beast Music's.")
    spotify_get.assert_not_called()
    user_request.assert_called_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={"context_uri": "spotify:playlist:user"},
    )

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  def test_tocar_playlist_a_partir_de_musica(self, _, user_request):
    user_request.side_effect = [
      {
        "items": [
          {
            "id": "playlist-id",
            "name": "Beast Music's",
            "uri": "spotify:playlist:user",
          }
        ]
      },
      {
        "items": [
          {
            "track": {
              "name": "Recairei",
              "uri": "spotify:track:1",
              "artists": [{"name": "Barões da Pisadinha"}],
            }
          }
        ],
        "next": None,
      },
      {},
    ]

    result = spotify.tocar_playlist_a_partir_de_musica("Best Musics", "barulhos da pisadinha")

    self.assertEqual(
      result,
      "Tocando sua playlist Beast Music's a partir de Recairei - Barões da Pisadinha.",
    )
    user_request.assert_called_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={
        "context_uri": "spotify:playlist:user",
        "offset": {"uri": "spotify:track:1"},
      },
    )

  @patch("Tools.spotify._spotify_user_request")
  def test_tocar_playlist_a_partir_de_musica_track_not_found(self, user_request):
    user_request.side_effect = [
      {
        "items": [
          {
            "id": "playlist-id",
            "name": "Best Music",
            "uri": "spotify:playlist:user",
          }
        ]
      },
      {
        "items": [
          {
            "track": {
              "name": "Tempo Perdido",
              "uri": "spotify:track:1",
              "artists": [{"name": "Legião Urbana"}],
            }
          }
        ],
        "next": None,
      },
    ]

    self.assertEqual(
      spotify.tocar_playlist_a_partir_de_musica("Best Music", "barulhos da pisadinha"),
      "Encontrei sua playlist Best Music, mas nao achei uma musica parecida com barulhos da pisadinha nela.",
    )

  @patch("Tools.spotify._spotify_get")
  @patch("Tools.spotify._spotify_user_request", return_value={"items": []})
  def test_tocar_playlist_empty_result(self, _, spotify_get):
    spotify_get.return_value = {"playlists": {"items": []}}
    self.assertEqual(spotify.tocar_playlist("nada"), "Nenhuma playlist encontrada.")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  def test_tocar_musicas_curtidas(self, _, user_request):
    self.assertEqual(spotify.tocar_musicas_curtidas(), "Tocando suas musicas curtidas.")
    user_request.assert_called_once_with(
      "/me/player/play",
      method="PUT",
      params={"device_id": "device-1"},
      body={"context_uri": "spotify:collection:tracks"},
    )

  @patch("Tools.spotify.platform.system", return_value="Windows")
  @patch("Tools.spotify.os.startfile")
  def test_abrir_busca_spotify_windows(self, startfile, _):
    self.assertEqual(
      spotify.abrir_busca_spotify("rock brasil"),
      "Buscando rock brasil no Spotify.",
    )
    startfile.assert_called_once_with("spotify:search:rock brasil")

  @patch("Tools.spotify._current_player", return_value={"is_playing": False})
  def test_pausar_musica_when_already_paused(self, _):
    self.assertEqual(spotify.pausar_musica(), "A musica ja estava pausada.")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  @patch("Tools.spotify._current_player", return_value={"is_playing": True})
  def test_pausar_musica_when_playing(self, *_):
    self.assertEqual(spotify.pausar_musica(), "Musica pausada.")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  def test_proxima_musica(self, *_):
    self.assertEqual(spotify.proxima_musica(), "Pulando para a proxima musica.")

  @patch("Tools.spotify._spotify_user_request")
  @patch("Tools.spotify._require_spotify_device", return_value="device-1")
  def test_musica_anterior(self, *_):
    self.assertEqual(spotify.musica_anterior(), "Voltando para a musica anterior.")

  @patch("Tools.spotify._set_volume")
  @patch("Tools.spotify._current_volume", return_value=95)
  def test_aumentar_volume_caps_at_100(self, _, set_volume):
    self.assertEqual(spotify.aumentar_volume(), "Volume aumentado para 100%.")
    set_volume.assert_called_once_with(100)

  @patch("Tools.spotify._set_volume")
  @patch("Tools.spotify._current_volume", return_value=5)
  def test_diminuir_volume_floors_at_0(self, _, set_volume):
    self.assertEqual(spotify.diminuir_volume(), "Volume diminuido para 0%.")
    set_volume.assert_called_once_with(0)

  @patch("Tools.spotify._current_volume", return_value=42)
  def test_volume_atual(self, _):
    self.assertEqual(spotify.volume_atual(), "Volume atual: 42%.")

  def test_format_spotify_restriction_error(self):
    message = spotify._format_spotify_error(
      403,
      '{"error":{"message":"Player command failed: Restriction violated"}}',
    )

    self.assertIn("Spotify recusou esse comando", message)

  @patch("Tools.spotify.get_spotify_user_access_token", return_value="x" * 32)
  def test_refresh_spotify_auth(self, get_token):
    spotify._user_token["access_token"] = "old"

    self.assertEqual(
      spotify.refresh_spotify_auth(),
      "Auth do Spotify atualizado sem abrir navegador.",
    )
    self.assertEqual(spotify._user_token, {})
    get_token.assert_called_once()

  @patch.dict("Tools.spotify.os.environ", {
    "CLIENT_ID": "client",
    "CLIENT_SECRET": "secret",
    "SPOTIFY_REFRESH_TOKEN": "refresh",
  })
  @patch("Tools.spotify._update_env_value")
  @patch("Tools.spotify._request_json")
  def test_get_spotify_user_access_token_persists_rotated_refresh_token(
    self,
    request_json,
    update_env_value,
  ):
    request_json.return_value = {
      "access_token": "x" * 32,
      "refresh_token": "new-refresh",
      "expires_in": 3600,
    }

    token = spotify.get_spotify_user_access_token()

    self.assertEqual(token, "x" * 32)
    update_env_value.assert_called_once_with("SPOTIFY_REFRESH_TOKEN", "new-refresh")


if __name__ == "__main__":
  unittest.main()
