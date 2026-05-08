from __future__ import annotations

from dotenv import load_dotenv
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import argparse
import base64
import ctypes
import json
import os
import platform
import re
import subprocess
import time
import unicodedata
import webbrowser
from ctypes import wintypes

from Config.transcription_fixes import lcs_similarity

load_dotenv()

_client_credentials_token: dict[str, str | float] = {}
_user_token: dict[str, str | float] = {}
MIN_TRACK_MATCH_SCORE = 50
MIN_PERSONAL_TRACK_MATCH_SCORE = 55
MIN_STRUCTURED_TITLE_MATCH_SCORE = 45
MIN_STRUCTURED_ARTIST_MATCH_SCORE = 25
PERSONAL_CATALOG_TTL_SECONDS = 600
PERSONAL_CATALOG_SAVED_TRACK_LIMIT = 300
PERSONAL_CATALOG_PLAYLIST_LIMIT = 20
PERSONAL_CATALOG_PLAYLIST_TRACK_LIMIT = 100
_personal_track_catalog_cache: dict[str, object] = {
  "expires_at": 0.0,
  "tracks": [],
}
SPOTIFY_SCOPES = [
  "user-read-playback-state",
  "user-modify-playback-state",
  "user-read-currently-playing",
  "user-library-read",
  "user-follow-read",
  "user-top-read",
  "playlist-read-private",
  "playlist-read-collaborative",
]


def _env(name: str, *fallbacks: str) -> str:
  for key in (name, *fallbacks):
    value = os.getenv(key)
    if value:
      return value
  return ""


def _request_json(
  url: str,
  method: str = "GET",
  headers: dict[str, str] | None = None,
  data: bytes | None = None
):
  request = Request(url, method=method, headers=headers or {}, data=data)

  try:
    with urlopen(request, timeout=15) as response:
      body = response.read().decode("utf-8")
      if response.status == 204:
        return {}
      if not body.strip():
        return {}
      try:
        return json.loads(body)
      except json.JSONDecodeError:
        return {}
  except HTTPError as error:
    body = error.read().decode("utf-8")
    raise RuntimeError(_format_spotify_error(error.code, body)) from error


def _format_spotify_error(status_code: int, body: str) -> str:
  try:
    payload = json.loads(body)
    error = payload.get("error", {})
    message = error.get("message", body)
    reason = error.get("reason")
  except json.JSONDecodeError:
    message = body
    reason = None

  if status_code == 403 and "Restriction violated" in message:
    return (
      "o Spotify recusou esse comando para o dispositivo atual. "
      "Isso costuma acontecer se a conta nao for Premium, se nao houver musica ativa, "
      "ou se o dispositivo nao aceitar controle remoto agora."
    )

  if status_code == 404:
    return "nao encontrei um player ativo no Spotify. Abra o Spotify no notebook e tente de novo."

  if status_code == 401:
    return "permissao do Spotify expirou ou esta invalida. Rode: python -m Tools.spotify auth"

  if status_code == 403 and "Insufficient client scope" in message:
    return "faltam permissoes no token do Spotify. Rode novamente: python -m Tools.spotify auth"

  if reason:
    return f"Erro Spotify {status_code}: {message} ({reason})"

  return f"Erro Spotify {status_code}: {message}"


def _spotify_client() -> tuple[str, str]:
  client_id = _env("CLIENT_ID", "SPOTIFY_CLIENT_ID")
  client_secret = _env("CLIENT_SECRET", "SPOTIFY_CLIENT_SECRET")

  if not client_id or not client_secret:
    raise RuntimeError("Configure CLIENT_ID e CLIENT_SECRET no .env.")

  return client_id, client_secret


def _basic_auth_header(client_id: str, client_secret: str) -> str:
  credentials = f"{client_id}:{client_secret}".encode("utf-8")
  return f"Basic {base64.b64encode(credentials).decode('utf-8')}"


def get_spotify_catalog_access_token() -> str:
  cached_token = _client_credentials_token.get("access_token")
  expires_at = float(_client_credentials_token.get("expires_at", 0))

  if cached_token and time.time() < expires_at:
    return str(cached_token)

  client_id, client_secret = _spotify_client()

  data = urlencode({
    "grant_type": "client_credentials",
  }).encode("utf-8")

  result = _request_json(
    "https://accounts.spotify.com/api/token",
    method="POST",
    headers={
      "Authorization": _basic_auth_header(client_id, client_secret),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    data=data,
  )

  _client_credentials_token["access_token"] = result["access_token"]
  _client_credentials_token["expires_at"] = time.time() + int(result.get("expires_in", 3600)) - 60

  return str(result["access_token"])


def get_spotify_access_token() -> str:
  return get_spotify_catalog_access_token()


def get_spotify_user_access_token() -> str:
  cached_token = _user_token.get("access_token")
  expires_at = float(_user_token.get("expires_at", 0))

  if cached_token and time.time() < expires_at:
    return str(cached_token)

  refresh_token = _env("SPOTIFY_REFRESH_TOKEN")
  if not refresh_token:
    raise RuntimeError(
      "Rode primeiro: python -m Tools.spotify auth"
    )

  client_id, client_secret = _spotify_client()
  data = urlencode({
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
  }).encode("utf-8")

  result = _request_json(
    "https://accounts.spotify.com/api/token",
    method="POST",
    headers={
      "Authorization": _basic_auth_header(client_id, client_secret),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    data=data,
  )

  if result.get("refresh_token"):
    _update_env_value("SPOTIFY_REFRESH_TOKEN", result["refresh_token"])

  _user_token["access_token"] = result["access_token"]
  _user_token["expires_at"] = time.time() + int(result.get("expires_in", 3600)) - 60

  return str(result["access_token"])


def refresh_spotify_auth() -> str:
  """Atualiza o access token do Spotify usando o refresh token salvo."""
  _user_token.clear()
  token = get_spotify_user_access_token()

  if len(token) <= 20:
    raise RuntimeError("nao consegui atualizar o token do Spotify.")

  return "Auth do Spotify atualizado sem abrir navegador."


def _spotify_get(path: str, params: dict[str, str | int]):
  token = get_spotify_catalog_access_token()
  url = f"https://api.spotify.com/v1{path}?{urlencode(params)}"

  return _request_json(
    url,
    headers={"Authorization": f"Bearer {token}"},
  )


def _spotify_user_request(
  path: str,
  method: str = "GET",
  params: dict[str, str | int] | None = None,
  body: dict | None = None
):
  token = get_spotify_user_access_token()
  query = f"?{urlencode(params)}" if params else ""
  data = json.dumps(body).encode("utf-8") if body is not None else None
  headers = {"Authorization": f"Bearer {token}"}

  if body is not None:
    headers["Content-Type"] = "application/json"

  return _request_json(
    f"https://api.spotify.com/v1{path}{query}",
    method=method,
    headers=headers,
    data=data,
  )


def _spotify_user_get(path: str, params: dict[str, str | int] | None = None):
  return _spotify_user_request(path, params=params)


def _update_env_value(key: str, value: str, env_path: str = ".env") -> None:
  lines = []
  found = False

  if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as file:
      lines = file.read().splitlines()

  for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
      lines[index] = f"{key}={value}"
      found = True
      break

  if not found:
    lines.append(f"{key}={value}")

  with open(env_path, "w", encoding="utf-8") as file:
    file.write("\n".join(lines) + "\n")

  os.environ[key] = value


def authorize_spotify_user() -> str:
  client_id, client_secret = _spotify_client()
  redirect_uri = _env("SPOTIFY_REDIRECT_URI") or "http://127.0.0.1:8888/callback"
  state = str(int(time.time()))

  auth_url = "https://accounts.spotify.com/authorize?" + urlencode({
    "response_type": "code",
    "client_id": client_id,
    "scope": " ".join(SPOTIFY_SCOPES),
    "redirect_uri": redirect_uri,
    "state": state,
  })

  print("Abrindo autorizacao do Spotify no navegador...")
  print("Se o navegador nao abrir, acesse esta URL:")
  print(auth_url)
  webbrowser.open(auth_url)

  redirected_url = input(
    "\nDepois de permitir, cole aqui a URL completa para onde o Spotify redirecionou:\n> "
  ).strip()

  parsed_url = urlparse(redirected_url)
  query = parse_qs(parsed_url.query)

  if query.get("state", [""])[0] != state:
    raise RuntimeError("State invalido. Refaca a autorizacao.")

  code = query.get("code", [""])[0]
  if not code:
    raise RuntimeError("Nao encontrei o parametro code na URL colada.")

  data = urlencode({
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": redirect_uri,
  }).encode("utf-8")

  result = _request_json(
    "https://accounts.spotify.com/api/token",
    method="POST",
    headers={
      "Authorization": _basic_auth_header(client_id, client_secret),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    data=data,
  )

  refresh_token = result.get("refresh_token")
  if not refresh_token:
    raise RuntimeError("Spotify nao retornou refresh_token.")

  _update_env_value("SPOTIFY_REDIRECT_URI", redirect_uri)
  _update_env_value("SPOTIFY_REFRESH_TOKEN", refresh_token)

  print("Permissao salva no .env como SPOTIFY_REFRESH_TOKEN.")
  return refresh_token


def abrir_spotify() -> str:
  """Abre o Spotify no computador do usuario."""
  if platform.system() == "Windows":
    spotify_pids = _windows_process_ids("Spotify.exe")
    if spotify_pids and _bring_windows_process_to_front(spotify_pids):
      return "Spotify em primeiro plano."

    os.startfile("spotify:")
  else:
    webbrowser.open("spotify:")

  return "Spotify aberto."


def _windows_process_ids(process_name: str) -> set[int]:
  result = subprocess.run(
    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
    capture_output=True,
    text=True,
    check=False,
  )

  if result.returncode != 0:
    return set()

  process_ids = set()

  for line in result.stdout.splitlines():
    parts = [part.strip('"') for part in line.split('","')]

    if len(parts) < 2 or parts[0].lower() != process_name.lower():
      continue

    try:
      process_ids.add(int(parts[1]))
    except ValueError:
      continue

  return process_ids


def _bring_windows_process_to_front(process_ids: set[int]) -> bool:
  user32 = ctypes.windll.user32
  windows = []

  enum_windows_proc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM,
  )

  def callback(hwnd, _):
    if not user32.IsWindowVisible(hwnd):
      return True

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

    if process_id.value in process_ids and user32.GetWindowTextLengthW(hwnd) > 0:
      windows.append(hwnd)
      return False

    return True

  user32.EnumWindows(enum_windows_proc(callback), 0)

  if not windows:
    return False

  hwnd = windows[0]
  user32.ShowWindow(hwnd, 9)
  return bool(user32.SetForegroundWindow(hwnd))


def abrir_uri_spotify(uri: str) -> str:
  """Abre uma tela especifica no app do Spotify."""
  if platform.system() == "Windows":
    os.startfile(uri)
  else:
    webbrowser.open(uri)

  return "Abrindo no Spotify."


def abrir_busca_spotify(termo: str) -> str:
  """Abre a busca do Spotify no app."""
  abrir_uri_spotify(f"spotify:search:{termo}")
  return f"Buscando {termo} no Spotify."


def fechar_spotify() -> str:
  """Fecha o Spotify no computador do usuario."""
  system = platform.system()

  if system == "Windows":
    result = subprocess.run(
      ["taskkill", "/IM", "Spotify.exe", "/F"],
      capture_output=True,
      text=True,
      check=False,
    )

    if result.returncode != 0:
      return "Spotify nao estava aberto."

    return "Spotify fechado."

  if system == "Darwin":
    subprocess.run(
      ["osascript", "-e", 'tell application "Spotify" to quit'],
      capture_output=True,
      text=True,
      check=False,
    )
    return "Spotify fechado."

  result = subprocess.run(
    ["pkill", "-f", "spotify"],
    capture_output=True,
    text=True,
    check=False,
  )

  if result.returncode != 0:
    return "Spotify nao estava aberto."

  return "Spotify fechado."


def buscar_musica(nome: str) -> str:
  """Busca musicas no catalogo do Spotify."""
  result = _spotify_get("/search", {
    "q": nome,
    "type": "track",
    "limit": 5,
    "market": "BR",
  })

  tracks = result.get("tracks", {}).get("items", [])
  if not tracks:
    return "Nenhuma musica encontrada."

  lines = []
  for track in tracks:
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    lines.append(f"{track['name']} - {artists} | uri: {track['uri']}")

  return "\n".join(lines)


def buscar_playlist(nome: str) -> str:
  """Busca playlists no catalogo do Spotify."""
  result = _spotify_get("/search", {
    "q": nome,
    "type": "playlist",
    "limit": 5,
    "market": "BR",
  })

  playlists = result.get("playlists", {}).get("items", [])
  playlists = [playlist for playlist in playlists if playlist]

  if not playlists:
    return "Nenhuma playlist encontrada."

  lines = []
  for playlist in playlists:
    owner = (playlist.get("owner") or {}).get("display_name", "Spotify")
    lines.append(f"{playlist['name']} - {owner} | uri: {playlist['uri']}")

  return "\n".join(lines)


def listar_minhas_playlists(limite: int = 10, detalhado: bool = False) -> str:
  """Lista playlists salvas/criadas pelo usuario."""
  result = _spotify_user_get("/me/playlists", {
    "limit": max(1, min(limite, 50)),
    "offset": 0,
  })
  playlists = result.get("items", [])
  playlists = [playlist for playlist in playlists if playlist]

  if not playlists:
    return "Nenhuma playlist encontrada na sua biblioteca."

  lines = []
  for playlist in playlists:
    if detalhado:
      owner = (playlist.get("owner") or {}).get("display_name", "Spotify")
      total = (playlist.get("tracks") or {}).get("total", 0)
      lines.append(f"{playlist['name']} - {owner} ({total} musicas) | uri: {playlist['uri']}")
    else:
      lines.append(playlist["name"])

  return "\n".join(lines)


def _minhas_playlists(limite: int = 50) -> list[dict]:
  result = _spotify_user_get("/me/playlists", {
    "limit": max(1, min(limite, 50)),
    "offset": 0,
  })
  playlists = result.get("items", [])
  return [playlist for playlist in playlists if playlist]


def _normalize_spotify_name(name: str) -> str:
  without_accents = unicodedata.normalize("NFD", name)
  without_accents = "".join(
    char for char in without_accents
    if unicodedata.category(char) != "Mn"
  )
  normalized = re.sub(r"[^a-zA-Z0-9]+", " ", without_accents.lower())
  words = []

  for word in normalized.split():
    if word == "s":
      continue

    if len(word) > 3 and word.endswith("s"):
      word = word[:-1]
    words.append(word)

  return " ".join(words)


def _remove_adjacent_duplicate_words(text: str) -> str:
  words = text.split()
  deduped_words = []
  previous_word = None

  for word in words:
    if word == previous_word:
      continue

    deduped_words.append(word)
    previous_word = word

  return " ".join(deduped_words)


def _longest_common_substring_score(left: str, right: str) -> int:
  return int(lcs_similarity(left, right) * 100)


def _unique_texts(values: list[str]) -> list[str]:
  unique_values = []
  seen = set()

  for value in values:
    normalized = _normalize_spotify_name(value)
    if not normalized or normalized in seen:
      continue

    unique_values.append(value.strip(" ,.!?:;\n\t"))
    seen.add(normalized)

  return unique_values


def _track_search_queries(query: str) -> list[str]:
  query = query.strip(" ,.!?:;\n\t")
  if not query:
    return []

  split_parts = [
    part.strip(" ,.!?:;\n\t")
    for part in re.split(r"[,;:/|]+", query)
    if part.strip(" ,.!?:;\n\t")
  ]
  queries = []

  if len(split_parts) > 1:
    queries.extend(reversed(split_parts))

  queries.append(query)
  queries.extend(split_parts)

  for part in split_parts or [query]:
    words = _normalize_spotify_name(part).split()
    if len(words) == 1 and len(words[0]) >= 6:
      queries.append(words[0][:4])

  return _unique_texts(queries)


def _structured_track_query_parts(query: str) -> list[str]:
  query = query.strip(" ,.!?:;\n\t")
  if not query:
    return []

  separator_parts = [
    part.strip(" ,.!?:;\n\t")
    for part in re.split(r"[,;:/|]+", query)
    if part.strip(" ,.!?:;\n\t")
  ]
  if len(separator_parts) >= 2:
    return _unique_texts(separator_parts)

  match = re.search(r"(.+?)\s+de\s+(.+)", query, flags=re.IGNORECASE)
  if match is not None:
    return _unique_texts([match.group(1), match.group(2)])

  return []


def _structured_track_assignment_score(
  parts: list[str],
  track_name: str,
  artists: str,
) -> int:
  if len(parts) < 2:
    return 0

  best_score = 0

  for title_part in parts:
    title_variants = [title_part]
    title_words = _normalize_spotify_name(title_part).split()
    if len(title_words) == 1 and len(title_words[0]) >= 6:
      title_variants.append(title_words[0][:4])

    title_score = max(_playlist_score(variant, track_name) for variant in title_variants)
    if title_score < MIN_STRUCTURED_TITLE_MATCH_SCORE:
      continue

    for artist_part in parts:
      if artist_part == title_part:
        continue

      artist_score = _playlist_score(artist_part, artists)
      if artist_score < MIN_STRUCTURED_ARTIST_MATCH_SCORE:
        continue

      best_score = max(
        best_score,
        min(100, title_score + min(15, artist_score // 6)),
      )

  return best_score


def _track_search_score(original_query: str, search_query: str, track: dict) -> int:
  if _structured_track_query_parts(original_query):
    return _track_score(original_query, track)

  return max(
    _track_score(original_query, track),
    _track_score(search_query, track),
  )


def _personal_track_score(query: str, track: dict) -> int:
  if _structured_track_query_parts(query):
    return _track_score(query, track)

  search_queries = _track_search_queries(query)
  if not search_queries:
    return 0

  return max(
    _track_score(search_query, track)
    for search_query in search_queries
  )


def _playlist_score(query: str, playlist_name: str) -> int:
  query = _remove_adjacent_duplicate_words(_normalize_spotify_name(query))
  playlist_name = _remove_adjacent_duplicate_words(_normalize_spotify_name(playlist_name))

  if query == playlist_name:
    return 100

  if query in playlist_name or playlist_name in query:
    return 90

  query_words = set(query.split())
  playlist_words = set(playlist_name.split())
  common_words = query_words & playlist_words

  if not query_words or not playlist_words:
    return 0

  word_score = int((len(common_words) / len(query_words)) * 80)
  substring_score = _longest_common_substring_score(query, playlist_name)

  return max(word_score, substring_score)


def _track_display_name(track: dict) -> str:
  artists = ", ".join(artist["name"] for artist in track.get("artists", []))
  if artists:
    return f"{track.get('name', 'Sem nome')} - {artists}"
  return track.get("name", "Sem nome")


def _track_score(query: str, track: dict) -> int:
  track_name = track.get("name", "")
  artists = " ".join(artist.get("name", "") for artist in track.get("artists", []))
  structured_parts = _structured_track_query_parts(query)
  normalized_query = _remove_adjacent_duplicate_words(_normalize_spotify_name(query))
  normalized_track_name = _remove_adjacent_duplicate_words(_normalize_spotify_name(track_name))
  normalized_artists = _remove_adjacent_duplicate_words(_normalize_spotify_name(artists))
  normalized_track_with_artists = " ".join(
    part for part in [normalized_track_name, normalized_artists]
    if part
  )

  if not normalized_query or not normalized_track_name:
    return 0

  query_words = set(normalized_query.split())
  track_words = set(normalized_track_name.split())
  artist_words = set(normalized_artists.split())

  track_name_score = _playlist_score(normalized_query, normalized_track_name)
  track_with_artists_score = _playlist_score(normalized_query, normalized_track_with_artists)
  artist_score = _playlist_score(normalized_query, normalized_artists) if normalized_artists else 0

  if normalized_track_name in normalized_query:
    track_name_score = max(track_name_score, 94)

  if track_words and track_words <= query_words:
    track_name_score = max(track_name_score, 92)

  artist_bonus = 0
  if artist_words and artist_words <= query_words:
    artist_bonus = 8

  if not structured_parts and track_name_score >= 85:
    return min(100, max(track_name_score, track_with_artists_score) + artist_bonus)

  extra_query_words = query_words - artist_words
  if not structured_parts and artist_score >= 90 and len(extra_query_words) <= 1:
    return artist_score

  score = max(
    track_with_artists_score,
    int((track_name_score * 0.75) + (artist_score * 0.25)),
  )

  if structured_parts:
    structured_score = _structured_track_assignment_score(
      structured_parts,
      normalized_track_name,
      normalized_artists,
    )

    if structured_score == 0:
      return min(score, 35)

    return max(score, structured_score)

  return score


def _buscar_minha_playlist(nome: str) -> dict | None:
  playlists = _minhas_playlists()
  best_playlist = None
  best_score = 0

  for playlist in playlists:
    score = _playlist_score(nome, playlist.get("name", ""))

    if score > best_score:
      best_playlist = playlist
      best_score = score

  if best_score >= 70:
    return best_playlist

  return None


def _playlist_id(playlist: dict) -> str | None:
  if playlist.get("id"):
    return playlist["id"]

  uri = playlist.get("uri", "")
  parts = uri.split(":")
  if len(parts) == 3 and parts[1] == "playlist":
    return parts[2]

  return None


def _playlist_tracks(playlist: dict, limite: int = 100) -> list[dict]:
  playlist_id = _playlist_id(playlist)
  if playlist_id is None:
    return []

  tracks = []
  offset = 0
  limit = max(1, min(limite, 100))

  while len(tracks) < limite:
    result = _spotify_user_get(f"/playlists/{playlist_id}/tracks", {
      "limit": limit,
      "offset": offset,
      "market": "BR",
      "fields": "items(track(name,uri,artists(name))),next",
    })
    items = result.get("items", [])
    if not isinstance(items, list):
      break

    for item in items:
      track = item.get("track") or {}
      if track.get("uri"):
        tracks.append(track)

    if not result.get("next") or not items:
      break

    offset += len(items)

  return tracks[:limite]


def _saved_tracks(limite: int = PERSONAL_CATALOG_SAVED_TRACK_LIMIT) -> list[dict]:
  tracks = []
  offset = 0

  while len(tracks) < limite:
    limit = min(50, limite - len(tracks))
    result = _spotify_user_get("/me/tracks", {
      "limit": limit,
      "offset": offset,
      "market": "BR",
    })
    items = result.get("items", [])
    if not isinstance(items, list):
      break

    for item in items:
      track = item.get("track") or {}
      if track.get("uri"):
        tracks.append(track)

    if not result.get("next") or not items:
      break

    offset += len(items)

  return tracks


def _dedupe_tracks(tracks: list[dict]) -> list[dict]:
  deduped_tracks = []
  seen_uris = set()

  for track in tracks:
    uri = track.get("uri")
    if not uri or uri in seen_uris:
      continue

    seen_uris.add(uri)
    deduped_tracks.append(track)

  return deduped_tracks


def _personal_track_catalog() -> list[dict]:
  expires_at = float(_personal_track_catalog_cache.get("expires_at") or 0)
  cached_tracks = _personal_track_catalog_cache.get("tracks")

  if time.time() < expires_at and isinstance(cached_tracks, list):
    return cached_tracks

  tracks = _saved_tracks(PERSONAL_CATALOG_SAVED_TRACK_LIMIT)

  for playlist in _minhas_playlists(PERSONAL_CATALOG_PLAYLIST_LIMIT):
    tracks.extend(_playlist_tracks(playlist, PERSONAL_CATALOG_PLAYLIST_TRACK_LIMIT))

  tracks = _dedupe_tracks(tracks)
  _personal_track_catalog_cache["tracks"] = tracks
  _personal_track_catalog_cache["expires_at"] = time.time() + PERSONAL_CATALOG_TTL_SECONDS

  return tracks


def _buscar_musica_no_catalogo_pessoal(nome: str) -> dict | None:
  try:
    tracks = _personal_track_catalog()
  except Exception:
    return None

  if not tracks:
    return None

  track = max(tracks, key=lambda item: _personal_track_score(nome, item))
  best_score = _personal_track_score(nome, track)

  if best_score >= MIN_PERSONAL_TRACK_MATCH_SCORE:
    return track

  return None


def _buscar_musica_na_playlist(playlist: dict, musica: str) -> dict | None:
  best_track = None
  best_score = 0

  for track in _playlist_tracks(playlist):
    score = _track_score(musica, track)

    if score > best_score:
      best_track = track
      best_score = score

  if best_score >= 50:
    return best_track

  return None


def listar_musicas_curtidas(limite: int = 10) -> str:
  """Lista musicas curtidas/salvas na biblioteca do usuario."""
  result = _spotify_user_get("/me/tracks", {
    "limit": max(1, min(limite, 50)),
    "offset": 0,
    "market": "BR",
  })
  items = result.get("items", [])

  if not items:
    return "Nenhuma musica curtida encontrada."

  lines = []
  for item in items:
    track = item.get("track") or {}
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    lines.append(f"{track.get('name', 'Sem nome')} - {artists} | uri: {track.get('uri')}")

  return "\n".join(lines)


def listar_artistas_seguidos(limite: int = 10) -> str:
  """Lista artistas seguidos pelo usuario."""
  result = _spotify_user_get("/me/following", {
    "type": "artist",
    "limit": max(1, min(limite, 50)),
  })
  artists = result.get("artists", {}).get("items", [])

  if not artists:
    return "Nenhum artista seguido encontrado."

  return "\n".join(
    f"{artist['name']} | uri: {artist['uri']}"
    for artist in artists
  )


def listar_meus_artistas(limite: int = 10) -> str:
  """Lista artistas mais ouvidos pelo usuario."""
  result = _spotify_user_get("/me/top/artists", {
    "limit": max(1, min(limite, 50)),
    "offset": 0,
    "time_range": "medium_term",
  })
  artists = result.get("items", [])

  if not artists:
    return "Nenhum artista frequente encontrado."

  return "\n".join(
    f"{artist['name']} | uri: {artist['uri']}"
    for artist in artists
  )


def listar_dispositivos() -> str:
  """Lista dispositivos disponiveis no Spotify."""
  devices = _spotify_user_request("/me/player/devices").get("devices", [])

  if not devices:
    return "Nenhum dispositivo ativo encontrado no Spotify."

  lines = []
  for device in devices:
    active = "ativo" if device.get("is_active") else "inativo"
    lines.append(f"{device['name']} ({device['type']}, {active})")

  return "\n".join(lines)


def _available_devices() -> list[dict]:
  return _spotify_user_request("/me/player/devices").get("devices", [])


def _current_player() -> dict:
  return _spotify_user_request("/me/player")


def _ensure_spotify_device() -> str | None:
  devices = _available_devices()

  if not devices:
    abrir_spotify()
    time.sleep(2)
    devices = _available_devices()

  if not devices:
    return None

  for device in devices:
    if device.get("is_active"):
      return device["id"]

  device_id = devices[0]["id"]
  _spotify_user_request(
    "/me/player",
    method="PUT",
    body={"device_ids": [device_id], "play": False},
  )

  return device_id


def _require_spotify_device() -> str:
  device_id = _ensure_spotify_device()

  if device_id is None:
    raise RuntimeError(
      "Nao encontrei dispositivo ativo. Abra o Spotify no notebook e deixe a conta logada."
    )

  return device_id


def tocar_musica(nome: str) -> str:
  """Busca e toca uma musica no Spotify."""
  personal_track = _buscar_musica_no_catalogo_pessoal(nome)
  if personal_track is not None:
    device_id = _require_spotify_device()
    _spotify_user_request(
      "/me/player/play",
      method="PUT",
      params={"device_id": device_id},
      body={"uris": [personal_track["uri"]]},
    )

    artists = ", ".join(artist["name"] for artist in personal_track.get("artists", []))
    return f"Tocando {personal_track['name']} - {artists}."

  candidates = []
  seen_uris = set()

  for search_query in _track_search_queries(nome):
    result = _spotify_get("/search", {
      "q": search_query,
      "type": "track",
      "limit": 10,
      "market": "BR",
    })

    for track in result.get("tracks", {}).get("items", []):
      uri = track.get("uri")
      if uri in seen_uris:
        continue

      seen_uris.add(uri)
      candidates.append((track, search_query))

  if not candidates:
    return "Nenhuma musica encontrada."

  track, search_query = max(
    candidates,
    key=lambda item: _track_search_score(nome, item[1], item[0]),
  )
  best_score = _track_search_score(nome, search_query, track)

  if best_score < MIN_TRACK_MATCH_SCORE:
    return f"Nao encontrei uma musica parecida com {nome}."

  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/play",
    method="PUT",
    params={"device_id": device_id},
    body={"uris": [track["uri"]]},
  )

  artists = ", ".join(artist["name"] for artist in track.get("artists", []))
  return f"Tocando {track['name']} - {artists}."


def tocar_playlist(nome: str) -> str:
  """Busca e toca uma playlist no Spotify."""
  playlist = _buscar_minha_playlist(nome)

  if playlist is not None:
    device_id = _require_spotify_device()
    _spotify_user_request(
      "/me/player/play",
      method="PUT",
      params={"device_id": device_id},
      body={"context_uri": playlist["uri"]},
    )

    return f"Tocando sua playlist {playlist['name']}."

  result = _spotify_get("/search", {
    "q": nome,
    "type": "playlist",
    "limit": 1,
    "market": "BR",
  })

  playlists = result.get("playlists", {}).get("items", [])
  playlists = [playlist for playlist in playlists if playlist]

  if not playlists:
    return "Nenhuma playlist encontrada."

  playlist = playlists[0]
  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/play",
    method="PUT",
    params={"device_id": device_id},
    body={"context_uri": playlist["uri"]},
  )

  return f"Tocando playlist {playlist['name']}."


def tocar_playlist_a_partir_de_musica(nome_playlist: str, musica: str) -> str:
  """Toca uma playlist do usuario comecando por uma musica dentro dela."""
  playlist = _buscar_minha_playlist(nome_playlist)

  if playlist is None:
    return f"Nao encontrei sua playlist {nome_playlist}."

  track = _buscar_musica_na_playlist(playlist, musica)
  if track is None:
    return f"Encontrei sua playlist {playlist['name']}, mas nao achei uma musica parecida com {musica} nela."

  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/play",
    method="PUT",
    params={"device_id": device_id},
    body={
      "context_uri": playlist["uri"],
      "offset": {"uri": track["uri"]},
    },
  )

  return f"Tocando sua playlist {playlist['name']} a partir de {_track_display_name(track)}."


def tocar_musicas_curtidas() -> str:
  """Toca a biblioteca de musicas curtidas do usuario."""
  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/play",
    method="PUT",
    params={"device_id": device_id},
    body={"context_uri": "spotify:collection:tracks"},
  )
  return "Tocando suas musicas curtidas."


def dar_play() -> str:
  """Continua a reproducao atual no Spotify."""
  player = _current_player()

  if player and player.get("is_playing"):
    return "A musica ja esta tocando."

  if not player or not player.get("item"):
    abrir_spotify()
    return "Spotify aberto. Escolha uma musica ou playlist para eu conseguir retomar."

  device_id = _require_spotify_device()

  try:
    _spotify_user_request(
      "/me/player/play",
      method="PUT",
      params={"device_id": device_id},
    )
  except RuntimeError as error:
    if "Spotify recusou esse comando" in str(error):
      return "Nao consegui retomar pelo controle remoto do Spotify. Abra uma musica no app e tente de novo."
    raise

  return "Dando play no Spotify."


def pausar_musica() -> str:
  """Pausa a musica atual no Spotify."""
  player = _current_player()
  if player and not player.get("is_playing"):
    return "A musica ja estava pausada."

  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/pause",
    method="PUT",
    params={"device_id": device_id},
  )
  return "Musica pausada."


def proxima_musica() -> str:
  """Pula para a proxima musica no Spotify."""
  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/next",
    method="POST",
    params={"device_id": device_id},
  )
  return "Pulando para a proxima musica."


def musica_anterior() -> str:
  """Volta para a musica anterior no Spotify."""
  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/previous",
    method="POST",
    params={"device_id": device_id},
  )
  return "Voltando para a musica anterior."


def aumentar_volume() -> str:
  """Aumenta o volume do Spotify."""
  volume = _current_volume()
  new_volume = min(volume + 10, 100)
  _set_volume(new_volume)
  return f"Volume aumentado para {new_volume}%."


def diminuir_volume() -> str:
  """Diminui o volume do Spotify."""
  volume = _current_volume()
  new_volume = max(volume - 10, 0)
  _set_volume(new_volume)
  return f"Volume diminuido para {new_volume}%."


def volume_atual() -> str:
  """Consulta o volume atual do Spotify."""
  return f"Volume atual: {_current_volume()}%."


def _current_volume() -> int:
  player = _spotify_user_request("/me/player")
  device = player.get("device") or {}
  volume = device.get("volume_percent")

  if volume is None:
    raise RuntimeError("Nao encontrei um dispositivo ativo no Spotify.")

  return int(volume)


def _set_volume(volume: int) -> None:
  device_id = _require_spotify_device()
  _spotify_user_request(
    "/me/player/volume",
    method="PUT",
    params={"volume_percent": volume, "device_id": device_id},
  )


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "command",
    choices=[
      "auth",
      "refresh",
      "token",
      "search",
      "playlist",
      "devices",
      "my-playlists",
      "liked",
      "followed-artists",
      "top-artists",
      "open-search",
    ],
  )
  parser.add_argument("query", nargs="*")
  args = parser.parse_args()

  if args.command == "auth":
    authorize_spotify_user()
    return

  if args.command == "refresh":
    print(refresh_spotify_auth())
    return

  if args.command == "token":
    token = get_spotify_user_access_token()
    print(f"user token ok: {len(token) > 20}")
    return

  if args.command == "search":
    print(buscar_musica(" ".join(args.query)))
    return

  if args.command == "playlist":
    print(buscar_playlist(" ".join(args.query)))
    return

  if args.command == "devices":
    print(listar_dispositivos())
    return

  if args.command == "my-playlists":
    print(listar_minhas_playlists(detalhado=True))
    return

  if args.command == "liked":
    print(listar_musicas_curtidas())
    return

  if args.command == "followed-artists":
    print(listar_artistas_seguidos())
    return

  if args.command == "top-artists":
    print(listar_meus_artistas())
    return

  if args.command == "open-search":
    print(abrir_busca_spotify(" ".join(args.query)))


if __name__ == "__main__":
  main()
