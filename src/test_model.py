from model import SourceClaim, ProductExtraction


def test_source_claim_model():
    claim = SourceClaim(
        value="IP65",
        source="manufacturer_datasheet",
        confidence="high",
        status="manufacturer_stated",
        notes="Explicitly stated in the datasheet.",
    )
    assert claim.source == "manufacturer_datasheet"
    assert claim.status == "manufacturer_stated"
    print("SourceClaim OK:", claim)


def test_product_extraction_model():
    extraction = ProductExtraction(
        model=[
            SourceClaim(
                value="SUN-5K-G06P3-EU-AM2-P1",
                source="manufacturer_datasheet",
                confidence="high",
                status="manufacturer_stated",
                notes="Model as stated in the datasheet.",
            )
        ],
        rated_power=[],
        manufacturer=[],
        factory_address=[],
        country_of_manufacture=[],
        ip_rating=[],
        weight=[],
        max_efficiency=[],
        grid_standards=[],
        safety_emc_standards=[],
        testing_evidence=[],
        labeling=[],
    )
    assert extraction.model[0].value == "SUN-5K-G06P3-EU-AM2-P1"
    print("ProductExtraction OK")


if __name__ == "__main__":
    test_source_claim_model()
    test_product_extraction_model()
    print("\nAll model tests passed.")
