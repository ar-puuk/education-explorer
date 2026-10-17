"""Download with sha256 + manifest. Raw files live in data-raw/ (gitignored)."""
from __future__ import annotations

import hashlib
import json
import time
import zipfile
from datetime import date
from pathlib import Path

import httpx

from .config import DATA_RAW, MANIFEST

UA = {"User-Agent": "Mozilla/5.0 (education-explorer pipeline)"}


def _load() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"files": []}


def _save(m: dict) -> None:
    m["files"].sort(key=lambda f: f["path"])
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def client() -> httpx.Client:
    return httpx.Client(headers=UA, follow_redirects=True, timeout=httpx.Timeout(60, read=600))


def download(url: str, rel: str, *, source: str, release: str = "",
             c: httpx.Client | None = None, skip_missing: bool = False) -> Path | None:
    """Download url to data-raw/<rel> unless present with a matching manifest hash.

    Returns the local path, or None when skip_missing and the server answers 404.
    A file already on disk but absent from the manifest is hashed and adopted.
    """
    dest = DATA_RAW / rel
    m = _load()
    entry = next((f for f in m["files"] if f["path"] == rel), None)
    if dest.exists():
        digest = sha256_file(dest)
        if entry and entry["sha256"] != digest:
            raise SystemExit(f"{rel}: local file hash differs from manifest; delete it or fix the manifest")
        if entry:
            return dest
        _record(rel, url, source, release, dest)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    own = c is None
    c = c or client()
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        for attempt in range(4):
            try:
                with c.stream("GET", url) as r:
                    if r.status_code == 404 and skip_missing:
                        return None
                    r.raise_for_status()
                    with tmp.open("wb") as f:
                        for chunk in r.iter_bytes(1 << 20):
                            f.write(chunk)
                break
            except httpx.HTTPError as e:
                if attempt == 3:
                    raise SystemExit(f"download failed: {url}: {e}") from e
                time.sleep(2 * (attempt + 1))
    finally:
        if own:
            c.close()
    tmp.replace(dest)
    _record(rel, url, source, release, dest)
    return dest


def _record(rel: str, url: str, source: str, release: str, dest: Path) -> None:
    m = _load()
    m["files"] = [f for f in m["files"] if f["path"] != rel]
    m["files"].append({
        "path": rel, "source": source, "url": url, "release": release,
        "sha256": sha256_file(dest), "bytes": dest.stat().st_size,
        "retrieved": date.today().isoformat(),
    })
    _save(m)


def unzip(zip_path: Path) -> Path:
    """Extract next to the zip into a folder named after it; returns the folder."""
    out = zip_path.with_suffix("")
    marker = out / ".extracted"
    if marker.exists():
        return out
    out.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(out)
    except NotImplementedError:
        # Deflate64 members (some large CCD files); the zipfile-deflate64 package is a drop-in
        import zipfile_deflate64

        with zipfile_deflate64.ZipFile(zip_path) as z:
            z.extractall(out)
    marker.write_text("ok")
    return out
