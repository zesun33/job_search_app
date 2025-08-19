import sys
import os
import glob
from typing import List

DOCS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "source_cover_letters"))


def ensure_directory_exists(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def extract_docx(path: str) -> str:
    try:
        from docx import Document  # type: ignore
    except Exception as import_error:  # pragma: no cover
        raise RuntimeError(
            "python-docx is required to extract .docx files. Install dependencies from requirements.txt."
        ) from import_error

    document = Document(path)
    paragraphs: List[str] = []
    for paragraph in document.paragraphs:
        paragraphs.append(paragraph.text)
    # Preserve simple paragraph separation
    return "\n\n".join([p for p in paragraphs if p is not None])


def extract_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as import_error:  # pragma: no cover
        raise RuntimeError(
            "pypdf is required to extract .pdf files. Install dependencies from requirements.txt."
        ) from import_error

    reader = PdfReader(path)
    pages_text: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    return "\n\n".join(pages_text)


def write_text(target_path: str, text: str) -> None:
    with open(target_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text.strip() + "\n")


def main() -> int:
    ensure_directory_exists(DOCS_DIR)

    patterns = [
        os.path.join(DOCS_DIR, "*.docx"),
        os.path.join(DOCS_DIR, "*.pdf"),
    ]

    files: List[str] = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    if not files:
        print(f"No source files found in: {DOCS_DIR}")
        return 0

    processed_count = 0
    for source_path in sorted(files):
        base, ext = os.path.splitext(source_path)
        target_txt = base + ".txt"
        try:
            if ext.lower() == ".docx":
                text = extract_docx(source_path)
            elif ext.lower() == ".pdf":
                text = extract_pdf(source_path)
            else:
                # Skip unknown extensions
                continue
            write_text(target_txt, text)
            processed_count += 1
            print(f"OK  -> {os.path.basename(source_path)} -> {os.path.basename(target_txt)}")
        except Exception as error:  # pragma: no cover
            print(f"FAIL-> {os.path.basename(source_path)}: {error}")

    print(f"Processed files: {processed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


