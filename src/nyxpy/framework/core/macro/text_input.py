"""Command text input validation."""


def validate_keyboard_text(text: str, allow_special: bool = True) -> str:
    """Controller text input として送信可能な文字列か検証します。"""
    if not text:
        raise ValueError("Input text is empty.")

    valid_ascii = {chr(i) for i in range(0x20, 0x7F)}
    if allow_special:
        valid_ascii.update(["\n", "\t"])

    for char in text:
        if char not in valid_ascii:
            raise ValueError(f"Unsupported character for keyboard input: {char!r}")

    return text
