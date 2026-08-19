from parsers.base_parser import clean_text, parse_weight_from_tokens, extract_text_lines


def test_clean_text_normalizes_whitespace_and_nbsp():
    s = " Hola\nMundo\u00A0 "
    assert clean_text(s) == "Hola Mundo"


def test_parse_weight_from_tokens_extracts_kg_and_lbs():
    tokens = ["PYRR-0001", "1000", "KG", "2204.62", "LBS"]
    kg, lbs, matches = parse_weight_from_tokens(tokens)
    assert kg == 1000
    assert abs(lbs - 2204.62) < 1e-6
    assert matches


def test_extract_text_lines_groups_words(sample_document):
    lines = extract_text_lines(sample_document, max_pages=1)
    # Expect at least header and BL line
    assert any("NAME OF SHIP" in l.upper() or "NAME" in l.upper() for l in lines)
    assert any("PYRR-0001" in l.upper() for l in lines)
