from pathlib import Path

from docx import Document

root = Path(".").resolve()
out_path = root / "project_export.docx"

include_exts = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".env",
    ".xml",
}
files = []
for path in root.rglob("*"):
    if path.is_file() and path.suffix.lower() in include_exts:
        if any(
            part in {"__pycache__", ".venv", "node_modules", ".git"}
            for part in path.parts
        ):
            continue
        files.append(path)

files = sorted(files, key=lambda p: str(p).lower())

doc = Document()
doc.add_heading("Project Export", level=1)
doc.add_paragraph("Generated from the workspace contents.")

for path in files:
    rel = path.relative_to(root).as_posix()
    doc.add_heading(rel, level=2)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="latin-1")
        except Exception:
            text = "[Binary or unreadable content]"

    for line in text.splitlines():
        safe_line = "".join(ch for ch in line if ch in "\t\n\r" or ch.isprintable())
        safe_line = safe_line.replace("\x00", "")
        if safe_line.strip():
            doc.add_paragraph(safe_line, style="List Bullet")
        else:
            doc.add_paragraph("")

doc.save(out_path)
print(out_path)
