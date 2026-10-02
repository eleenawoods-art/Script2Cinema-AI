import re


def detect_scenes(script: str):
    if not script.strip():
        return []

    heading_pattern = re.compile(
        r"(?im)^(scene\s+\d+|int\.|ext\.|chapter\s+\d+|سین\s*\d+).*$"
    )

    matches = list(heading_pattern.finditer(script))

    if matches:
        scenes = []

        for i, match in enumerate(matches):
            start = match.start()
            end = (
                matches[i + 1].start()
                if i + 1 < len(matches)
                else len(script)
            )

            scenes.append(
                {
                    "number": i + 1,
                    "title": match.group(0).strip(),
                    "text": script[start:end].strip(),
                }
            )

        return scenes

    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n\s*\n+", script)
        if block.strip()
    ]

    if not blocks:
        blocks = [script.strip()]

    return [
        {
            "number": i + 1,
            "title": f"Scene {i + 1}",
            "text": block,
        }
        for i, block in enumerate(blocks)
    ]


def detect_characters(script: str):
    characters = []

    patterns = [
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{1,40})\s*:\s+",
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{1,40})\s*-\s+",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, script):
            name = match.group(1).strip()

            if name and name not in characters:
                characters.append(name)

    return characters


def count_dialogues(script: str):
    pattern = (
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}"
        r"\s*:\s+.+$"
    )

    return len(re.findall(pattern, script))


def estimate_duration(script: str):
    words = len(
        re.findall(
            r"\b[\w'-]+\b",
            script,
        )
    )

    return words / 130 if words else 0


def clean_dialogue_text(text: str):
    text = re.sub(
        r"(?im)^\s*"
        r"(scene\s+\d+|int\.|ext\.|chapter\s+\d+|سین\s*\d+)"
        r".*$",
        "",
        text,
    )

    text = re.sub(
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}\s*:\s*",
        "",
        text,
    )

    text = re.sub(
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}\s*-\s*",
        "",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()
