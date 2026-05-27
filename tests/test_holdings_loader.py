from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_news.holdings_loader import holding_terms_for_gosb, holdings_display_for_gosb, load_holdings, parse_holding_line, terms_for_holdings

sample = "Самарский ГОСБ|ГК СДМ|ООО \"СДМ\"; ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \"СДМ\"|6312345678|Развитие"
holding = parse_holding_line(sample)
assert holding.gosb == "Самарский ГОСБ"
assert holding.name == "ГК СДМ"
assert "ООО \"СДМ\"" in holding.aliases
assert "6312345678" in holding.inns
terms = terms_for_holdings([holding])
assert "гк сдм" in terms
assert "сдм" not in terms
assert "6312345678" in terms

fd, path = tempfile.mkstemp(prefix="holdings-test-", suffix=".txt")
Path(path).write_text("# comment\n" + sample + "\n", encoding="utf-8")
try:
    loaded = load_holdings(path)
    assert len(loaded) == 1
    assert "гк сдм" in holding_terms_for_gosb("Самарский ГОСБ", path=path)
    assert holdings_display_for_gosb("Самарский ГОСБ", path=path) == "ГК СДМ"
finally:
    Path(path).unlink(missing_ok=True)

print("holdings_loader ok")
