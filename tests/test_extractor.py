from ground_truth.agents import extractor


def test_extract_claims_parses_and_reassigns_ids(monkeypatch):
    fake_payload = {
        "claims": [
            {
                "id": "whatever",
                "text": "SpaceX was founded by Elon Musk in 2002.",
                "original_sentence": "SpaceX was founded by Elon Musk in 2002.",
                "checkable": True,
                "claim_type": "factual",
            },
            {
                "id": "whatever2",
                "text": "SpaceX is the most impressive company of our generation.",
                "original_sentence": "I think it's the most impressive company.",
                "checkable": False,
                "claim_type": "opinion",
            },
        ]
    }

    monkeypatch.setattr(
        extractor, "structured_call", lambda prompt, schema: schema.model_validate(fake_payload)
    )

    claims = extractor.extract_claims("SpaceX was founded by Elon Musk in 2002. I think it's great.")

    assert [c.id for c in claims] == ["c1", "c2"]
    assert claims[0].checkable is True
    assert claims[1].checkable is False
    assert claims[1].claim_type == "opinion"


def test_extract_claims_empty_text(monkeypatch):
    monkeypatch.setattr(
        extractor,
        "structured_call",
        lambda prompt, schema: schema.model_validate({"claims": []}),
    )
    assert extractor.extract_claims("") == []
