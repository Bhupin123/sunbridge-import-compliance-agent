from pathlib import Path
import fitz


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_pdf(file_path: Path) -> str:
    """Extract text from a PDF."""
    document = fitz.open(file_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()

        pages.append(
            f"\n--- Page {page_number} ---\n{text}"
        )

    document.close()

    return "\n".join(pages)


def load_text_file(file_path: Path) -> str:
    """Read a text source."""
    return file_path.read_text(encoding="utf-8")


def load_sources() -> dict:
    """Load all three Task 2 sources."""

    datasheet_path = DATA_DIR / "manufacturer_datasheet.pdf"
    buyer_form_path = DATA_DIR / "buyer_form.txt"
    call_notes_path = DATA_DIR / "call_notes.txt"

    sources = {
        "manufacturer_datasheet": load_pdf(datasheet_path),
        "buyer_form": load_text_file(buyer_form_path),
        "call_notes": load_text_file(call_notes_path),
    }

    return sources


if __name__ == "__main__":
    sources = load_sources()

    for source_name, content in sources.items():
        print("\n" + "=" * 60)
        print(source_name.upper())
        print("=" * 60)
        print(content[:2000])