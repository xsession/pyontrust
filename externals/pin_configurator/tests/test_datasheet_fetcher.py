# SPDX-License-Identifier: Apache-2.0

from datasheet_fetcher import _build_search_queries, _candidate_matches_part, _catalog_terms, _extract_search_urls, _prefer_search_before_direct, _score_search_url, identify_vendor


def test_extract_search_urls_prefers_decoded_duckduckgo_targets():
    html = '''
    <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.st.com%2Fresource%2Fen%2Fdatasheet%2Fstm32f446re.pdf&amp;rut=abc">ST PDF</a>
    <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.st.com%2Fen%2Fmicrocontrollers-microprocessors%2Fstm32f446%2Fdocumentation.html&amp;rut=def">Docs</a>
    '''

    urls = _extract_search_urls(html)

    assert "https://www.st.com/resource/en/datasheet/stm32f446re.pdf" in urls
    assert "https://www.st.com/en/microcontrollers-microprocessors/stm32f446/documentation.html" in urls


def test_score_search_url_prefers_vendor_pdf_with_matching_part():
    vendor_pdf = _score_search_url("https://www.st.com/resource/en/datasheet/stm32f446re.pdf", "st", "stm32f446xx")
    vendor_doc = _score_search_url("https://www.st.com/en/microcontrollers-microprocessors/stm32f446/documentation.html", "st", "stm32f446xx")
    vendor_ref = _score_search_url("https://www.st.com/resource/en/reference_manual/rm0390-stm32f446xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf", "st", "stm32f446xx")
    third_party_pdf = _score_search_url("https://example.com/pdf/stm32f446xx.pdf", "st", "stm32f446xx")

    assert vendor_pdf < vendor_doc
    assert vendor_pdf < vendor_ref
    assert vendor_pdf < third_party_pdf


def test_score_search_url_prefers_canonical_st_host_and_english_resource_path():
    canonical = _score_search_url(
        "https://www.st.com/resource/en/datasheet/stm32f427vg.pdf",
        "st",
        "stm32f427",
    )
    localized_host = _score_search_url(
        "https://www.st.com.cn/resource/zh/datasheet/stm32f427vg.pdf",
        "st",
        "stm32f427",
    )
    localized_path = _score_search_url(
        "https://www.st.com/resource/zh/datasheet/stm32f427vg.pdf",
        "st",
        "stm32f427",
    )

    assert canonical < localized_host
    assert canonical < localized_path


def test_score_search_url_prefers_microchip_family_datasheet_over_generic_pdf():
    family_pdf = _score_search_url(
        "https://ww1.microchip.com/downloads/en/DeviceDoc/SAM-C20-C21-Family-Data-Sheet-DS60001479J.pdf",
        "microchip",
        "samc21n18a",
    )
    generic_pdf = _score_search_url(
        "https://ww1.microchip.com/downloads/en/DeviceDoc/70005318A.pdf",
        "microchip",
        "samc21n18a",
    )

    assert family_pdf < generic_pdf


def test_identify_vendor_supports_stm32mp_parts():
    result = identify_vendor("stm32mp135fxx")

    assert result is not None
    assert result.vendor == "st"
    assert result.vendor_name == "STMicroelectronics"
    assert result.family == "STM32MP1"
    assert "https://www.st.com/resource/en/datasheet/stm32mp135fxx.pdf" in result.datasheet_urls


def test_identify_vendor_prefers_xx_family_url_for_bare_stm32_parts():
    result = identify_vendor("stm32f427")

    assert result is not None
    assert result.vendor == "st"
    assert result.datasheet_urls[0] == "https://www.st.com/resource/en/datasheet/stm32f427xx.pdf"
    assert "https://www.st.com/resource/en/datasheet/stm32f427.pdf" in result.datasheet_urls


def test_prefer_search_before_direct_for_bare_stm32_family_inputs():
    assert _prefer_search_before_direct("stm32f427", identify_vendor("stm32f427"))
    assert not _prefer_search_before_direct("stm32f427vg", identify_vendor("stm32f427vg"))
    assert not _prefer_search_before_direct("stm32mp135fxx", identify_vendor("stm32mp135fxx"))


def test_identify_vendor_supports_microchip_samc_parts():
    result = identify_vendor("samc21n18a")

    assert result is not None
    assert result.vendor == "microchip"
    assert result.vendor_name == "Microchip Technology"
    assert result.family == "SAMC21"


def test_build_search_queries_for_unknown_parts_uses_generic_terms():
    queries = _build_search_queries("npcx4m8f", None)

    assert queries
    assert any(query.lower() == "npcx4m8f datasheet pdf" for query in queries)
    assert any(query.lower() == "npcx4m8f mcu datasheet pdf" for query in queries)
    assert any(query.lower() == "npcx4m8 datasheet pdf" for query in queries)


def test_build_search_queries_for_st_parts_adds_vendor_and_site_queries():
    vendor = identify_vendor("stm32mp135fxx")

    queries = _build_search_queries("stm32mp135fxx", vendor)

    assert any(query.lower() == "stm32mp135fxx stmicroelectronics datasheet pdf" for query in queries)
    assert any(query.lower() == "site:www.st.com stm32mp135fxx datasheet pdf" for query in queries)


def test_build_search_queries_for_microchip_samc_adds_family_aliases():
    vendor = identify_vendor("samc21n18a")

    queries = _build_search_queries("samc21n18a", vendor)

    assert any(query.lower() == "sam c20/c21 family data sheet pdf" for query in queries)
    assert any(query.lower() == "samc21n18a microchip technology datasheet pdf" for query in queries)
    assert any(query.lower() == "atsamc21n18a datasheet pdf" for query in queries)


def test_catalog_terms_resolve_family_profile_metadata():
    vendor = identify_vendor("samc21n18a")

    terms = _catalog_terms("samc21n18a", vendor)

    assert "ATSAMC21N18A" in terms.aliases
    assert "SAM C20/C21 Family Data Sheet" in terms.aliases
    assert "SAM C20/C21 Family Data Sheet" in terms.title_tokens
    assert any(query.lower() == "sam c20/c21 family data sheet pdf" for query in terms.preferred_queries)


def test_candidate_matches_part_rejects_unrelated_pdf_for_unknown_vendor():
    assert not _candidate_matches_part(
        "https://www.nxp.com/docs/en/data-sheet/MC9S08SC4.pdf",
        "MC9S08SC4 Data Sheet",
        "npcx4m8f",
        None,
    )


def test_candidate_matches_part_accepts_microchip_family_datasheet_title():
    vendor = identify_vendor("samc21n18a")

    assert _candidate_matches_part(
        "https://ww1.microchip.com/downloads/en/DeviceDoc/SAM-C20-C21-Family-Data-Sheet-DS60001479J.pdf",
        "SAM C20/C21 Family Data Sheet - Microchip Technology",
        "samc21n18a",
        vendor,
    )