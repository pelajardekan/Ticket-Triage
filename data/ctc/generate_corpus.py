#!/usr/bin/env python3
"""
Build a Custom Text Classification training corpus from data/seed_tickets.json.

Custom Text Classification needs:
  * one .txt file per document, all at the ROOT of a blob container
  * a labels JSON file describing which class each document belongs to
  * at least 10 documents in total

This script writes both into data/ctc/out/, ready to upload:

    python data/ctc/generate_corpus.py
    az storage blob upload-batch \
        --account-name <storage> --destination <container> \
        --source data/ctc/out/documents --auth-mode login

Then import data/ctc/out/labels.json in Azure AI Foundry / Language Studio.

NOTE ON CLASS BALANCE: 18 seed tickets across 6 classes is below what you want
for a model you would trust. Microsoft's guidance is at least 50 examples per
class. Have each team member write 10 more tickets per category before you
train; a thin corpus is the single most common reason a student model performs
worse than the keyword baseline.
"""

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED_FILE = ROOT / "data" / "seed_tickets.json"
OUT = HERE / "out"
DOCS = OUT / "documents"

PROJECT_NAME = "TicketTriage"
CONTAINER_NAME = "tickettriage-training"


def slug(value: str) -> str:
    """Document names allow letters and numbers only, with no spaces."""
    return re.sub(r"[^A-Za-z0-9]", "", value)[:40] or "doc"


def main() -> None:
    seeds = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    DOCS.mkdir(parents=True, exist_ok=True)
    for stale in DOCS.glob("*.txt"):
        stale.unlink()

    documents = []
    classes = {}

    for index, seed in enumerate(seeds, start=1):
        label = seed.get("expected", "General Enquiry")
        classes[label] = classes.get(label, 0) + 1
        filename = f"ticket{index:03d}{slug(label)}.txt"
        (DOCS / filename).write_text(f"{seed['title']}. {seed['description']}", encoding="utf-8")
        documents.append({
            "location": filename,
            "language": "en",
            "dataset": "Train" if index % 5 else "Test",
            "class": {"category": label},
        })

    labels = {
        "projectFileVersion": "2022-05-01",
        "stringIndexType": "Utf16CodeUnit",
        "metadata": {
            "projectKind": "CustomSingleLabelClassification",
            "storageInputContainerName": CONTAINER_NAME,
            "projectName": PROJECT_NAME,
            "multilingual": False,
            "description": "AI-200 capstone ticket categories",
            "language": "en",
        },
        "assets": {
            "projectKind": "CustomSingleLabelClassification",
            "classes": [{"category": c} for c in sorted(classes)],
            "documents": documents,
        },
    }

    (OUT / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")

    print(f"Wrote {len(documents)} documents to {DOCS}")
    print(f"Wrote labels file to {OUT / 'labels.json'}")
    print("\nDocuments per class:")
    for label in sorted(classes):
        warn = "  <-- too few, add more" if classes[label] < 10 else ""
        print(f"  {label:<22} {classes[label]}{warn}")


if __name__ == "__main__":
    main()
