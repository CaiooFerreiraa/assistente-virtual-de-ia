import unittest

from Config.transcription_fixes import (
  apply_transcription_fixes,
  lcs_similarity,
)


class TranscriptionFixesTest(unittest.TestCase):
  def test_fixes_agent_name_alias_at_wake_position(self):
    self.assertEqual(
      apply_transcription_fixes("Estiu abra o espachai"),
      "Steel abra o espachai",
    )

  def test_does_not_map_music_or_artist_names(self):
    self.assertEqual(
      apply_transcription_fixes("toca Akashi Cruiz"),
      "toca Akashi Cruiz",
    )

  def test_does_not_map_hallucinated_song_phrases(self):
    self.assertEqual(
      apply_transcription_fixes("Steel toca Toxicity e desiste do Fadão"),
      "Steel toca Toxicity e desiste do Fadão",
    )

  def test_keeps_unrelated_text(self):
    self.assertEqual(
      apply_transcription_fixes("isso nao deveria mudar muito"),
      "isso nao deveria mudar muito",
    )

  def test_lcs_similarity_scores_close_words(self):
    self.assertGreater(lcs_similarity("Akashi Cruiz", "Akashi Cruz"), 0.8)

  def test_does_not_replace_song_title_still_when_it_is_not_wake_word(self):
    self.assertEqual(
      apply_transcription_fixes("toca Still Loving You"),
      "toca Still Loving You",
    )


if __name__ == "__main__":
  unittest.main()
