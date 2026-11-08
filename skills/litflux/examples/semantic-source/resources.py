"""Resource examples, supplied to LitFlux as source text only."""
from pathlib import Path


def save_report(directory, config, connection, storage, text):
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    report_file = folder / "report.txt"
    report_file.write_text(text, encoding=config.get("encoding", "utf-8"))
    connection.execute("INSERT INTO reports(body) VALUES (?)", (text,))
    recent = []
    recent.append(str(report_file))
    storage.save(recent)
    return recent
