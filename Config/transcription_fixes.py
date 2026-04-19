import re
import unicodedata
from pathlib import Path

TRAINING_FILE = Path(__file__).with_name("transcription_training.txt")

DEFAULT_TRANSCRIPTION_FIXES = {
  "espachai": "spotify",
  "spotifai": "spotify",
  "spotfy": "spotify",
  "estiu": "Steel",
  "estil": "Steel",
  "still": "Steel",
  "stil": "Steel",
  "mosca": "música",
  "cache cruise": "Akashi Cruz",
  "akashi cruise": "Akashi Cruz",
  "sistema fandal": "system of a down",
  "sistema fandals": "system of a down",
  "caixa cruz": "Akashi Cruz",
  "Cache Cruz": "Akashi Cruz",
  "Kashi Cruz": "Akashi Cruz",
  "Acácio Cruz": "Akashi Cruz",
  "Acacio Cruz": "Akashi Cruz",
  "Bacaxi Cruz": "Akashi Cruz",
  "Baka Cruz": "Akashi Cruz",
  "Bakashi Cruz": "Akashi Cruz",
  "Tox City.": "Toxcity",
  "Toxiri": "Toxcity",
  "toxiti": "Toxcity",
}

DEFAULT_FUZZY_TERMS = {
  "Spotify": 0.72,
  "Steel": 0.58,
  "Akashi Cruz": 0.62,
  "System of a Down": 0.58,
  "Toxcity": 0.48,
  "Legião Urbana": 0.68,
  "Filho do Piseiro": 0.68,
}

_training_cache = {
  "mtime": None,
  "exact": DEFAULT_TRANSCRIPTION_FIXES,
  "fuzzy": DEFAULT_FUZZY_TERMS,
  "exact_patterns": None,
}


def parse_training_file(path: Path = TRAINING_FILE) -> tuple[dict[str, str], dict[str, float]]:
  if not path.exists():
    return DEFAULT_TRANSCRIPTION_FIXES.copy(), DEFAULT_FUZZY_TERMS.copy()

  exact_fixes: dict[str, str] = {}
  fuzzy_terms: dict[str, float] = {}
  section = None

  for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()

    if not line or line.startswith("#"):
      continue

    if line.lower() == "[exact]":
      section = "exact"
      continue

    if line.lower() == "[fuzzy]":
      section = "fuzzy"
      continue

    if "=>" not in line:
      continue

    left, right = [part.strip() for part in line.split("=>", 1)]

    if not left or not right:
      continue

    if section == "exact":
      exact_fixes[left] = right
    elif section == "fuzzy":
      try:
        fuzzy_terms[left] = float(right)
      except ValueError:
        continue

  return exact_fixes or DEFAULT_TRANSCRIPTION_FIXES.copy(), fuzzy_terms or DEFAULT_FUZZY_TERMS.copy()


def load_training() -> tuple[dict[str, str], dict[str, float], list[tuple[re.Pattern, str]]]:
  mtime = TRAINING_FILE.stat().st_mtime if TRAINING_FILE.exists() else None

  if _training_cache["mtime"] == mtime and _training_cache["exact_patterns"] is not None:
    return (
      _training_cache["exact"],
      _training_cache["fuzzy"],
      _training_cache["exact_patterns"],
    )

  exact_fixes, fuzzy_terms = parse_training_file(TRAINING_FILE)
  exact_patterns = [
    (re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", flags=re.IGNORECASE), correct)
    for wrong, correct in sorted(
      exact_fixes.items(),
      key=lambda item: len(item[0]),
      reverse=True,
    )
  ]

  _training_cache["mtime"] = mtime
  _training_cache["exact"] = exact_fixes
  _training_cache["fuzzy"] = fuzzy_terms
  _training_cache["exact_patterns"] = exact_patterns

  return exact_fixes, fuzzy_terms, exact_patterns


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


def _candidate_windows(words: list[str], term: str):
  term_size = len(term.split())
  min_size = max(1, term_size - 1)
  max_size = min(len(words), term_size)

  for size in range(max_size, min_size - 1, -1):
    for start in range(0, len(words) - size + 1):
      end = start + size
      yield start, end, " ".join(words[start:end])


def apply_lcs_fuzzy_terms(text: str) -> str:
  _, fuzzy_terms, _ = load_training()
  words = text.split()

  if not words:
    return text

  index = 0
  fixed_words = []

  while index < len(words):
    best_match = None

    for term, threshold in fuzzy_terms.items():
      for start, end, candidate in _candidate_windows(words[index:], term):
        if start != 0:
          continue

        score = lcs_similarity(candidate, term)
        common_size = longest_common_substring_size(
          normalize_for_lcs(candidate),
          normalize_for_lcs(term),
        )

        if score >= threshold and common_size >= 4:
          size = end - start
          if best_match is None or size > best_match[0] or score > best_match[1]:
            best_match = (size, score, term)

    if best_match is not None:
      size, _, term = best_match
      fixed_words.append(term)
      index += size
    else:
      fixed_words.append(words[index])
      index += 1

  return " ".join(fixed_words)


def apply_transcription_fixes(text: str) -> str:
  fixed_text = text
  _, _, exact_patterns = load_training()

  for pattern, correct in exact_patterns:
    fixed_text = pattern.sub(correct, fixed_text)

  fixed_text = " ".join(fixed_text.split())
  return apply_lcs_fuzzy_terms(fixed_text)
