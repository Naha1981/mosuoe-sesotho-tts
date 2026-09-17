from evaluation.evaluate_asr import edit_distance, normalize


def test_normalize_removes_punctuation_and_normalizes_case():
    assert normalize("Lumela, KE KOpa!") == ["lumela", "ke", "kopa"]


def test_edit_distance_counts_word_errors():
    substitutions, insertions, deletions = edit_distance(
        ["ke", "a", "bua"],
        ["ke", "bua", "le"]
    )
    assert substitutions == 1
    assert insertions == 1
    assert deletions == 1
