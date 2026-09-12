#!/usr/bin/env python3
"""Catalog author identity comes from verified slugs, not shared names."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_catalog import group_translations


def translation(author, language="gr"):
    return {"title": "A work", "author": author, "language": language,
            "language_name": language, "html_path": f"{language}/work.html"}


class CatalogAuthorTests(unittest.TestCase):
    def test_verified_identity_shares_only_primary_names(self):
        authority = {"authors": {"first-writer": {}, "second-writer": {}},
                     "stem_overrides": {"curated": "first-writer"}}
        inputs = {
            "curated": [translation("Ποιητής"), translation("Translator instrumentation", "en")],
            "one--first-writer": [translation("Shared Name")],
            "two--second-writer": [translation("Shared Name")],
            "three--unverified": [translation("Ποιητής")],
            "unmapped": [translation("Shared Name")],
        }
        with patch("author_data.load_authors", return_value=authority):
            works = {work["id"]: work for work in group_translations(inputs)}
        first = works["curated"]
        self.assertEqual(first.get("author_id"), "first-writer")
        self.assertEqual(first["author"], "Ποιητής")
        self.assertEqual(set(first["author_aliases"]), {"Ποιητής", "Shared Name", "First Writer"})
        self.assertEqual(first["author_aliases"], works["one--first-writer"]["author_aliases"])
        self.assertEqual(set(works["two--second-writer"]["author_aliases"]), {"Shared Name", "Second Writer"})
        for key in ("three--unverified", "unmapped"):
            self.assertNotIn("author_id", works[key])
            self.assertNotIn("author_aliases", works[key])

    def test_real_curated_homer_mapping(self):
        works = group_translations({"homeric-epigrams": [translation("Ὅμηρος")],
                                    "iliad--homer": [translation("Homer")]})
        self.assertEqual({work.get("author_id") for work in works}, {"homer"})
        self.assertTrue(all(set(work["author_aliases"]) == {"Ὅμηρος", "Homer"} for work in works))


if __name__ == "__main__":
    unittest.main()
