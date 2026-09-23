"""Fetch the two Commons illustrations; attribution is in explore.ART."""
import hashlib
from pathlib import Path
import sys
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learngeo.explore import ART

if __name__ == "__main__":
    for filename, title, _ in ART.values():
        title = title.replace(" ", "_")
        digest = hashlib.md5(title.encode()).hexdigest()
        url = f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{quote(title)}"
        response = requests.get(url, timeout=25, headers={"User-Agent": "LearnGeo/0.1 educational atlas"})
        response.raise_for_status()
        if b"<svg" not in response.content or b"<script" in response.content.lower():
            raise ValueError("Expected a static SVG illustration")
        (ROOT / "static" / "images" / filename).write_bytes(response.content)
        print(filename, len(response.content))
