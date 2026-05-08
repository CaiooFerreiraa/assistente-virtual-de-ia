import re
import unicodedata

AGENT_NAME = "Steel"
AGENT_NAME_ALIASES = ("steel", "estiu", "estil", "still", "stil", "steele", "estilo")
WAKE_PREFIXES = ("", "oi", "ei", "hey", "ok", "ola", "olá")


def normalize_for_lcs(text: str) -> str:
  normalized = unicodedata.normalize("NFD", text)
  normalized = "".join(
    char for char in normalized
    if unicodedata.category(char) != "Mn"
  )
  normalized = re.sub(r"[^a-zA-Z0-9 ]+", " ", normalized)
  return " ".join(normalized.lower().split())


def longest_common_substring_size(left: str, right: str) -> int:
  if not left or not right:
    return 0

  previous = [0] * (len(right) + 1)
  best = 0

  for left_index in range(1, len(left) + 1):
    current = [0] * (len(right) + 1)

    for right_index in range(1, len(right) + 1):
      if left[left_index - 1] == right[right_index - 1]:
        current[right_index] = previous[right_index - 1] + 1
        best = max(best, current[right_index])

    previous = current

  return best


def lcs_similarity(left: str, right: str) -> float:
  normalized_left = normalize_for_lcs(left)
  normalized_right = normalize_for_lcs(right)

  if not normalized_left or not normalized_right:
    return 0.0

  common_size = longest_common_substring_size(normalized_left, normalized_right)
  return (2 * common_size) / (len(normalized_left) + len(normalized_right))


def _is_wake_word_position(text: str, start: int) -> bool:
  prefix = normalize_for_lcs(text[:start]).strip()
  return prefix in WAKE_PREFIXES


def apply_transcription_fixes(text: str) -> str:
  fixed_text = " ".join(text.split())

  for alias in AGENT_NAME_ALIASES:
    pattern = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", flags=re.IGNORECASE)
    match = pattern.search(fixed_text)

    if match is not None and _is_wake_word_position(fixed_text, match.start()):
      return f"{fixed_text[:match.start()]}{AGENT_NAME}{fixed_text[match.end():]}"

  return fixed_text
