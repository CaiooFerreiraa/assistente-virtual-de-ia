import re
import unicodedata

DEFAULT_WAKE_WORD_ALIASES = ["Steel", "Still", "Stil", "Estil", "estiu", "Steele", "estilo"]
INCOMPLETE_COMMAND_ENDINGS = [
  " pra",
  " para",
  " de",
  " do",
  " da",
  " dos",
  " das",
  " toca",
  " tocar",
  " toque",
  " coloca",
  " coloque",
]
STANDALONE_COMMAND_WORDS = [
  "abrir",
  "abre",
  "fechar",
  "fecha",
  "pausar",
  "pausa",
  "proxima",
  "próxima",
  "anterior",
  "volume",
  "spotify",
  "playlist",
  "retoma",
]
MUSIC_FILLERS = [
  "para mim",
  "pra mim",
  "por favor",
  "alguma musica de",
  "alguma musica do",
  "alguma musica da",
  "alguma música de",
  "alguma música do",
  "alguma música da",
  "uma musica de",
  "uma musica do",
  "uma musica da",
  "uma música de",
  "uma música do",
  "uma música da",
  "musica de",
  "musica do",
  "musica da",
  "música de",
  "música do",
  "música da",
]


def normalize_message(message: str) -> str:
  return " ".join(message.strip(" ,.!?:;\n\t").split())


def normalize_for_match(message: str) -> str:
  without_accents = unicodedata.normalize("NFD", message)
  without_accents = "".join(
    char for char in without_accents
    if unicodedata.category(char) != "Mn"
  )
  return normalize_message(without_accents).lower()


def extract_message_after_wake_word(message: str, wake_words: list[str]) -> str | None:
  escaped_words = [re.escape(wake_word) for wake_word in wake_words]
  pattern = rf"\b({'|'.join(escaped_words)})\b"
  match = re.search(pattern, message, flags=re.IGNORECASE)

  if match is None:
    return None

  message_after_wake_word = message[match.end():].strip(" ,.!?:;\n\t")
  if message_after_wake_word:
    return message_after_wake_word

  message_before_wake_word = message[:match.start()].strip(" ,.!?:;\n\t")

  return message_before_wake_word or message


def is_probably_incomplete_command(message: str) -> bool:
  normalized = normalize_message(message).lower()

  if not normalized:
    return True

  if any(normalized.endswith(ending) for ending in INCOMPLETE_COMMAND_ENDINGS):
    return True

  words = normalized.split()
  if len(words) <= 2 and not any(word in normalized for word in STANDALONE_COMMAND_WORDS):
    return True

  return False


def join_command_parts(parts: list[str]) -> str:
  return normalize_message(" ".join(part for part in parts if part))


def remove_wake_words(message: str) -> str:
  if not message:
    return message

  escaped_words = [re.escape(wake_word) for wake_word in DEFAULT_WAKE_WORD_ALIASES]
  pattern = rf"\b({'|'.join(escaped_words)})\b"
  return normalize_message(re.sub(pattern, " ", message, flags=re.IGNORECASE))


def clean_music_query(message: str) -> str:
  query = remove_wake_words(message)
  query = re.sub(
    r"\b(toca|toque|tocar|coloca|coloque|bota|bote)\b",
    "",
    query,
    count=1,
    flags=re.IGNORECASE,
  )

  for filler in MUSIC_FILLERS:
    query = re.sub(re.escape(filler), " ", query, flags=re.IGNORECASE)

  return normalize_message(query)


def clean_playlist_query(message: str) -> str:
  query = remove_wake_words(message)
  query = re.sub(
    r"\b(toca|toque|tocar|coloca|coloque|bota|bote|abre|abrir)\b",
    "",
    query,
    count=1,
    flags=re.IGNORECASE,
  )
  query = re.sub(
    r"\b(a|uma|minha|minhas|meu|meus|playlist|playlists|lista|listas)\b",
    " ",
    query,
    flags=re.IGNORECASE,
  )

  for filler in MUSIC_FILLERS:
    query = re.sub(re.escape(filler), " ", query, flags=re.IGNORECASE)

  return normalize_message(query)


def clean_playlist_track_query(message: str) -> str:
  query = normalize_message(message)
  query = re.sub(
    r"^(pela musica de|pela musica do|pela musica da|pela musica|"
    r"pela música de|pela música do|pela música da|pela música|"
    r"a partir da musica de|a partir da música de|a partir de|"
    r"a musica de|a música de|musica de|música de|pela|pelo|por)\b",
    " ",
    query,
    flags=re.IGNORECASE,
  )
  return normalize_message(query)


def extract_playlist_track_request(message: str) -> tuple[str, str] | None:
  query = normalize_for_match(remove_wake_words(message))
  action_words = (
    "comeca|comece|comecar|inicia|inicie|iniciar|"
    "coloca|coloque|bota|bote|toca|toque|tocar"
  )
  patterns = [
    rf"(?:dentro da|dentro de|na|no)\s+(?:minha\s+|meu\s+)?playlist\s+(.+?)[, ]+\s*(?:{action_words})\s+(.+)",
    rf"(?:minha\s+|meu\s+)?playlist\s+(.+?)[, ]+\s*(?:{action_words})\s+(.+)",
  ]

  for pattern in patterns:
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if match is None:
      continue

    playlist_name = clean_playlist_query(match.group(1))
    track_query = clean_playlist_track_query(match.group(2))

    if playlist_name and track_query:
      return playlist_name, track_query

  return None
