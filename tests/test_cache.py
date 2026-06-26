from core.cache import make_key


def test_cache_key_includes_model_version():
    key_v1 = make_key("hello world", model_version="v1")
    key_v2 = make_key("hello world", model_version="v2")
    assert key_v1 != key_v2, "Different model versions must produce different cache keys"


def test_cache_key_same_input_same_version():
    key1 = make_key("hello world", model_version="v1")
    key2 = make_key("hello world", model_version="v1")
    assert key1 == key2


def test_cache_key_normalizes_text():
    key1 = make_key("  Hello World  ", model_version="v1")
    key2 = make_key("hello world", model_version="v1")
    assert key1 == key2, "Text should be stripped and lowercased"


def test_cache_key_different_text():
    key1 = make_key("hello", model_version="v1")
    key2 = make_key("world", model_version="v1")
    assert key1 != key2
