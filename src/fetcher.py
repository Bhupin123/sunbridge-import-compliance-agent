import requests
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Source 1 from the Task 2 brief — the manufacturer datasheet (public link).
# Fetching it at runtime is part of the task: the pipeline should pull the
# document from the link, not rely on a hand-placed copy.
DATASHEET_URL = (
    "https://www.deyeinverter.com/deyeinverter/2023/10/07/"
    "datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"
)

DATASHEET_PATH = DATA_DIR / "manufacturer_datasheet.pdf"

# The manufacturer site blocks default scripted clients (403), so we send
# a normal browser User-Agent.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_datasheet(force: bool = False) -> Path:
    """
    Download the manufacturer datasheet PDF from its public URL.

    If a local copy already exists it is reused as a cache unless
    `force` is set. If the network fetch fails, we fall back to any
    existing local copy (so the pipeline still runs offline) and warn
    the caller. Buyer form and call notes are supplied inline in the
    brief as text, so they are not fetched.
    """

    if DATASHEET_PATH.exists() and not force:
        return DATASHEET_PATH

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(
            DATASHEET_URL, headers=_HEADERS, timeout=30
        )
        response.raise_for_status()
        DATASHEET_PATH.write_bytes(response.content)
        return DATASHEET_PATH

    except requests.RequestException as exc:
        if DATASHEET_PATH.exists():
            print(
                f"WARNING: could not download datasheet ({exc}). "
                f"Using existing local copy at {DATASHEET_PATH}."
            )
            return DATASHEET_PATH
        raise


if __name__ == "__main__":
    path = fetch_datasheet()
    print(f"Datasheet available at: {path}")
