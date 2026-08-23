from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.result_classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if "avm-result" in classes:
            self.result_classes.extend(classes)

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text.append(stripped)


class CommandCenterCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "command-center-card.html").read_text(encoding="utf-8")
        cls.parser = CardParser()
        cls.parser.feed(cls.source)
        cls.text = " ".join(cls.parser.text)

    def test_card_has_requested_title_and_matrix_axes(self) -> None:
        self.assertIn("AIP × Verifier Matrix", self.text)
        for label in [
            "Identity",
            "Authority",
            "Presenter",
            "Scope",
            "Action",
            "Provenance",
            "Freshness",
            "Independence",
            "Carrier",
            "Verifier",
            "Binding",
            "Failure",
            "Result",
        ]:
            self.assertIn(label, self.text)

    def test_card_has_all_four_mapping_states(self) -> None:
        for state in ["exact", "declared-gap", "ambiguous", "unrepresented"]:
            self.assertIn(state, self.parser.result_classes)

    def test_card_has_all_four_negative_tiles(self) -> None:
        for title in [
            "Wrong Presenter",
            "Same-Control Verifier",
            "Stale/Unverifiable Completion",
            "A2A→MCP Action Swap",
        ]:
            self.assertIn(title, self.text)

    def test_card_has_requested_timing_metadata(self) -> None:
        for value in ["Confidence 98", "Window NOW", "AIP-01 Aug 19", "Principal Binding-06 Aug 17", "agentproto WG forming"]:
            self.assertIn(value, self.text)

    def test_green_semantics_are_explicit(self) -> None:
        self.assertIn("Green means the distinction is faithfully represented.", self.text)
        self.assertIn("signature automatically establishes", self.text)


if __name__ == "__main__":
    unittest.main()
