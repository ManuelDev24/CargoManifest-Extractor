from parsers.local_parser import LocalManifestParser


def test_local_parser_finds_bl_and_parses_header(sample_document):
    parser = LocalManifestParser()
    records = parser.parse(sample_document)
    # Should find at least one record for PYRR-0001
    assert records, "No records returned"
    bls = [r.bl_number for r in records if r.bl_number]
    assert any(b.upper() == "PYRR-0001" for b in bls)
    # Header fields should be present
    rec0 = records[0]
    assert rec0.ship_name is not None or rec0.voyage is not None
