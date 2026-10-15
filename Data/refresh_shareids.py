"""
Re-downloads the full genshin-db repo and rebuilds action_shareids.json and
character_shareids.json from scratch. Run this whenever a new game update adds
cards that are missing from your current dicts.

Usage: python refresh_shareids.py
"""

import json
import glob
import os
import tarfile
import urllib.request
import tempfile

REPO_TARBALL_URL = "https://codeload.github.com/theBowja/genshin-db/tar.gz/refs/heads/main"
ACTION_OUT = "action_shareids.json"
CHARACTER_OUT = "character_shareids.json"


def download_repo(dest_path):
    print("Downloading genshin-db repo (this is ~45MB, may take a minute)...")
    urllib.request.urlretrieve(REPO_TARBALL_URL, dest_path)
    print("Download complete.")


def extract_tcg_folders(tarball_path, extract_to):
    print("Extracting TCG card data...")
    with tarfile.open(tarball_path, "r:gz") as tar:
        members = [
            m for m in tar.getmembers()
            if "/src/data/English/tcgactioncards/" in m.name
            or "/src/data/English/tcgcharactercards/" in m.name
        ]
        tar.extractall(path=extract_to, members=members)
    print(f"Extracted {len(members)} files.")


def build_map(root_dir, folder_name):
    result = {}
    pattern = os.path.join(root_dir, "*", "src", "data", "English", folder_name, "*.json")
    for path in glob.glob(pattern):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("name")
        shareid = data.get("shareid")
        if name and shareid is not None and name not in result:
            result[name] = shareid
    return result


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tarball_path = os.path.join(tmpdir, "genshin-db.tar.gz")
        download_repo(tarball_path)
        extract_tcg_folders(tarball_path, tmpdir)

        action_cards = build_map(tmpdir, "tcgactioncards")
        character_cards = build_map(tmpdir, "tcgcharactercards")

    with open(ACTION_OUT, "w", encoding="utf-8") as f:
        json.dump(action_cards, f, indent=2)
    with open(CHARACTER_OUT, "w", encoding="utf-8") as f:
        json.dump(character_cards, f, indent=2)

    print(f"\nSaved {len(action_cards)} action cards -> {ACTION_OUT}")
    print(f"Saved {len(character_cards)} character cards -> {CHARACTER_OUT}")


if __name__ == "__main__":
    main()
