from pathlib import Path
import tempfile
import unittest

from Config import transcription_fixes
from Config.transcription_fixes import (
  apply_transcription_fixes,
  lcs_similarity,
  parse_training_file,
)


class TranscriptionFixesTest(unittest.TestCase):
  def test_applies_exact_fixes_from_training_file(self):
    self.assertEqual(
      apply_transcription_fixes("Estiu abra o espachai"),
      "Steel abra o Spotify",
    )

  def test_applies_lcs_fuzzy_terms(self):
    self.assertEqual(
      apply_transcription_fixes("toca Akashi Cruiz"),
      "toca Akashi Cruz",
    )

  def test_keeps_unrelated_text(self):
    self.assertEqual(
      apply_transcription_fixes("isso nao deveria mudar muito"),
      "isso nao deveria mudar muito",
    )

  def test_lcs_similarity_scores_close_words(self):
    self.assertGreater(lcs_similarity("Akashi Cruiz", "Akashi Cruz"), 0.8)

  def test_parse_training_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      training_file = Path(temp_dir) / "training.txt"
      training_file.write_text(
        """
        [exact]
        errado => correto

        [fuzzy]
        Nome Certo => 0.61
        """,
        encoding="utf-8",
      )

      exact_fixes, fuzzy_terms = parse_training_file(training_file)

    self.assertEqual(exact_fixes["errado"], "correto")
    self.assertEqual(fuzzy_terms["Nome Certo"], 0.61)

  def tearDown(self):
    transcription_fixes._training_cache["mtime"] = None
    transcription_fixes._training_cache["exact_patterns"] = None


if __name__ == "__main__":
  unittest.main()
