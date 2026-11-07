"""Small reference routines, read statically by the layout examples."""


def report(text):
    words = text.strip().split()
    metrics = {"count": len(words), "unique": len(set(words))}
    return f"{metrics['count']} words, {metrics['unique']} unique"


def inspect_words(words):
    count = len(words)
    unique = len(set(words))
    return {"count": count, "unique": unique}


def accept(words):
    if words:
        return len(words)
    return "No words"


def collect(words):
    counts = []
    for word in words:
        counts.append(len(word))
    return counts
