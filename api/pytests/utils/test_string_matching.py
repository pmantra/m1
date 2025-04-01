import pytest

from utils.string_matching import hamming_distance


@pytest.mark.parametrize(
    "str1, str2, expected_distance",
    [
        ("", "", 0),  # Empty strings
        ("abc", "abc", 0),  # Equal strings
        ("abc", "abd", 1),  # Single character difference
        ("abc", "abcde", 2),  # Different lengths
        ("abcd", "abde", 2),  # Same lengths with a difference
        ("abc", "def", 3),  # Completely different strings
        ("abcdef", "fedcba", 6),  # Reversed strings
        ("hello", "world", 4),  # Different strings of same length
    ],
)
def test_hamming_distance(str1, str2, expected_distance):
    assert hamming_distance(str1, str2) == expected_distance


# Test case for non-string input
def test_hamming_distance__non_string_input():
    with pytest.raises(TypeError):
        hamming_distance(123, "abc")
