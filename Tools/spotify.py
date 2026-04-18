from __future__ import annotations

from dotenv import load_dotenv
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import argparse
import base64
import json
import os
import platform
import subprocess
import time
import webbrowser

load_dotenv()

_client_credentials_token: dict[str, str | float] = {}
_user_token: dict[str, str | float] = {}
SPOTIFY_SCOPES = [
  "user-read-playback-state",
  "user-modify-playback-state",
  "user-read-currently-playing",
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
      if not body:
        return {}
      return json.loads(body)
  except HTTPError as error:
    body = error.read().decode("utf-8")
    raise RuntimeError(f"Erro Spotify {error.code}: {body}") from error


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

  _user_token["access_token"] = result["access_token"]
  _user_token["expires_at"] = time.time() + int(result.get("expires_in", 3600)) - 60

  return str(result["access_token"])


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
    os.startfile("spotify:")
  else:
    webbrowser.open("spotify:")

  return "Spotify aberto."


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


def tocar_musica(nome: str) -> str:
  """Busca e toca uma musica no Spotify."""
  result = _spotify_get("/search", {
    "q": nome,
    "type": "track",
    "limit": 1,
    "market": "BR",
  })

  tracks = result.get("tracks", {}).get("items", [])
  if not tracks:
    return "Nenhuma musica encontrada."

  track = tracks[0]
  _spotify_user_request(
    "/me/player/play",
    method="PUT",
    body={"uris": [track["uri"]]},
  )

  artists = ", ".join(artist["name"] for artist in track.get("artists", []))
  return f"Tocando {track['name']} - {artists}."


def pausar_musica() -> str:
  """Pausa a musica atual no Spotify."""
  _spotify_user_request("/me/player/pause", method="PUT")
  return "Musica pausada."


def proxima_musica() -> str:
  """Pula para a proxima musica no Spotify."""
  _spotify_user_request("/me/player/next", method="POST")
  return "Pulando para a proxima musica."


def musica_anterior() -> str:
  """Volta para a musica anterior no Spotify."""
  _spotify_user_request("/me/player/previous", method="POST")
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
  _spotify_user_request(
    "/me/player/volume",
    method="PUT",
    params={"volume_percent": volume},
  )


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("command", choices=["auth", "token", "search"])
  parser.add_argument("query", nargs="*")
  args = parser.parse_args()

  if args.command == "auth":
    authorize_spotify_user()
    return

  if args.command == "token":
    token = get_spotify_user_access_token()
    print(f"user token ok: {len(token) > 20}")
    return

  if args.command == "search":
    print(buscar_musica(" ".join(args.query)))


if __name__ == "__main__":
  main()
