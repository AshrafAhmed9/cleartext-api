from worker.model import predict_batch


def test_comment_longer_than_the_model_limit_is_classified():
    """The model reads at most 512 tokens. Longer comments must be cut off, not crash."""
    long_comment = "you are terrible and I hate this so much " * 100  # about 900 tokens

    [result] = predict_batch([long_comment])

    assert result["prediction"] in ("toxic", "non-toxic")


def test_long_comment_does_not_break_the_comments_batched_with_it():
    results = predict_batch(["have a great day", "you are terrible " * 200])

    assert len(results) == 2
