from utils.passwords import (
    FEEDBACK_MISSING_ATTRIBUTE,
    FEEDBACK_PASSWORD_SHORT,
    check_password_strength,
)


class TestPasswordStrengthCheck:
    @staticmethod
    def test_check_password_strength():
        # Given
        pw = "AbCd1234!?"
        expected = {
            "score": 40.0,
            "password_strength_score": 4.0,
            "password_strength_ok": True,
            "feedback": [],
            "password_length": len(pw),
        }
        # When
        actual = check_password_strength(pw)
        # Then
        assert actual == expected

    @staticmethod
    def test_check_too_weak():
        # Given
        pw = "AbCdAbCdAbCd"
        expected = {
            "score": 0.0,
            "password_strength_score": 0.0,
            "password_strength_ok": False,
            "feedback": [FEEDBACK_MISSING_ATTRIBUTE],
            "password_length": len(pw),
        }
        # When
        actual = check_password_strength(pw)
        # Then
        assert actual == expected

    @staticmethod
    def test_check_too_short():
        # Given
        pw = "AbCd"
        expected = {
            "score": 0.0,
            "password_strength_score": 0.0,
            "password_strength_ok": False,
            "feedback": [FEEDBACK_PASSWORD_SHORT],
            "password_length": len(pw),
        }
        # When
        actual = check_password_strength(pw)
        # Then
        assert actual == expected
