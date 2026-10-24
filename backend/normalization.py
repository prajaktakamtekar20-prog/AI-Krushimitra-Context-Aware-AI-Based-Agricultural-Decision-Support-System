import re


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def normalize_mobile(value: str) -> str:
    digits = "".join(character for character in value if character.isascii() and character.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not INDIAN_MOBILE_PATTERN.fullmatch(digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    return digits