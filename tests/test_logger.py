from src.utils.logger import sanitize_for_log


def test_sanitize_for_log_strips_newlines_and_carriage_returns():
    assert sanitize_for_log("run_123\nFAKE LOG LINE: admin logged in") == (
        "run_123FAKE LOG LINE: admin logged in"
    )
    assert sanitize_for_log("a\r\nb") == "ab"


def test_sanitize_for_log_leaves_normal_values_unchanged():
    assert sanitize_for_log("run_1783414603_2b797f99f0bee74f") == (
        "run_1783414603_2b797f99f0bee74f"
    )


def test_sanitize_for_log_coerces_non_string_values():
    assert sanitize_for_log(None) == "None"
    assert sanitize_for_log(404) == "404"
