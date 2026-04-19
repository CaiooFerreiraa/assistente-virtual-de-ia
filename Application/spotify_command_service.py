import re

from Domain.voice_commands import (
  clean_music_query,
  clean_playlist_query,
  extract_playlist_track_request,
  normalize_for_match,
  normalize_message,
)
from Tools.spotify import (
  abrir_busca_spotify,
  abrir_spotify,
  aumentar_volume,
  dar_play,
  diminuir_volume,
  fechar_spotify,
  listar_artistas_seguidos,
  listar_dispositivos,
  listar_meus_artistas,
  listar_minhas_playlists,
  listar_musicas_curtidas,
  musica_anterior,
  pausar_musica,
  proxima_musica,
  tocar_musica,
  tocar_musicas_curtidas,
  tocar_playlist,
  tocar_playlist_a_partir_de_musica,
  volume_atual,
)


def execute_spotify_command(message: str) -> str | None:
  normalized = normalize_for_match(message)

  if "dispositivo" in normalized or "devices" in normalized:
    return listar_dispositivos()

  if "busca" in normalized or "pesquisa" in normalized or "procurar" in normalized:
    query = re.sub(r"\b(busca|buscar|pesquisa|pesquisar|procura|procurar|spotify|no|na|o|a)\b", " ", message, flags=re.IGNORECASE)
    query = normalize_message(query)
    if query:
      return abrir_busca_spotify(query)

  if "playlist" in normalized or "playlists" in normalized or "lista" in normalized:
    playlist_track_request = extract_playlist_track_request(message)
    if playlist_track_request is not None:
      playlist_name, track_query = playlist_track_request
      return tocar_playlist_a_partir_de_musica(playlist_name, track_query)

    wants_to_play_playlist = any(
      word in normalized
      for word in ["toca", "toque", "tocar", "coloca", "coloque", "bota", "bote", "abre", "abrir"]
    )
    should_list_playlists = (
      not wants_to_play_playlist
      and (
      "minhas playlists" in normalized
      or "minhas playlist" in normalized
      or "minha playlist" in normalized
      or "listar playlists" in normalized
      or "listar playlist" in normalized
      or "mostrar playlists" in normalized
      or "mostrar playlist" in normalized
      or "mostra playlists" in normalized
      or "mostra playlist" in normalized
      or "quais playlists" in normalized
      or "quais playlist" in normalized
      or "nomes das minhas playlists" in normalized
      or "nome das minhas playlists" in normalized
      or normalized.strip() in ["playlists", "playlist", "minhas listas", "minha lista"]
      )
    )

    if should_list_playlists:
      return listar_minhas_playlists()

    query = clean_playlist_query(message)
    if query:
      return tocar_playlist(query)

  if any(phrase in normalized for phrase in ["musicas curtidas", "musica curtida", "curtidas", "biblioteca"]):
    if any(word in normalized for word in ["toca", "tocar", "toque", "coloca", "bota"]):
      return tocar_musicas_curtidas()

    return listar_musicas_curtidas()

  if "artistas seguidos" in normalized or "artista seguido" in normalized:
    return listar_artistas_seguidos()

  if "meus artistas" in normalized or "artistas favoritos" in normalized or "artistas mais ouvidos" in normalized:
    return listar_meus_artistas()

  if "spotify" in normalized and any(word in normalized for word in ["abre", "abrir", "abrir o"]):
    return abrir_spotify()

  if "spotify" in normalized and any(word in normalized for word in ["fecha", "fechar"]):
    return fechar_spotify()

  if any(word in normalized for word in ["pausa", "pausar", "pause"]):
    return pausar_musica()

  if any(phrase in normalized for phrase in ["dar play", "da play", "de play", "continua", "continuar", "retoma", "retomar"]):
    return dar_play()

  if any(word in normalized for word in ["proxima", "passa", "pula"]):
    return proxima_musica()

  if "anterior" in normalized or "volta" in normalized:
    return musica_anterior()

  if "volume" in normalized and any(word in normalized for word in ["aumenta", "aumentar", "sobe", "subir"]):
    return aumentar_volume()

  if "volume" in normalized and any(word in normalized for word in ["diminui", "diminuir", "abaixa", "baixar"]):
    return diminuir_volume()

  if "volume" in normalized:
    return volume_atual()

  if any(word in normalized for word in ["toca", "toque", "tocar", "coloca", "coloque", "bota", "bote"]):
    query = clean_music_query(message)
    if query:
      return tocar_musica(query)

  return None
