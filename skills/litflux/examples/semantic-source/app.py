"""Small source-backed authoring example, unrelated to any evaluation project."""
from pathlib import Path


def normalize(text):
    return text.strip()


def write_text(path, text):
    Path(path).write_text(text, encoding="utf-8")
    return str(path)


def submit(text, path, writer=write_text):
    cleaned = normalize(text)
    if not cleaned:
        return {"saved": False, "location": None}
    location = writer(path, cleaned)
    return {"saved": True, "location": location}


def submit_many(texts, path, writer=write_text):
    results = []
    for text in texts:
        results.append(submit(text, path, writer))
    return results
