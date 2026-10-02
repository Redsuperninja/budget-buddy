"""Tests for the tax-year reference data files and loader."""

import json
from decimal import Decimal
from importlib import resources
from typing import Any

import pytest
from pydantic import ValidationError

from app.tax_data import (
    FILING_STATUSES,
    TaxYearData,
    UnsupportedTaxYearError,
    load_tax_year,
    supported_tax_years,
)

YEARS = (2025, 2026)


def _raw(year: int) -> dict[str, Any]:
    text = resources.files("app.tax_data").joinpath(f"{year}.json").read_text(encoding="utf-8")
    return json.loads(text)


def _walk(node: Any, path: str = ""):
    """Yield (path, key, value) for every key/value in nested dicts and lists."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _walk(item, f"{path}[{i}]")


def test_supported_years_include_2025_and_2026() -> None:
    assert set(YEARS) <= set(supported_tax_years())


@pytest.mark.parametrize("year", YEARS)
def test_schema_loads(year: int) -> None:
    data = load_tax_year(year)
    assert isinstance(data, TaxYearData)
    assert data.tax_year == year


@pytest.mark.parametrize("year", YEARS)
@pytest.mark.parametrize("table", ["ordinary_brackets", "capital_gains_brackets"])
def test_brackets_ascend_and_end_with_null(year: int, table: str) -> None:
    by_status = getattr(load_tax_year(year), table).by_filing_status
    assert set(by_status) == set(FILING_STATUSES)
    for brackets in by_status.values():
        limits = [b.up_to_cents for b in brackets]
        assert limits[-1] is None
        assert all(limit is not None for limit in limits[:-1])
        assert limits[:-1] == sorted(limits[:-1])
        assert len(set(limits[:-1])) == len(limits) - 1
        rates = [b.rate for b in brackets]
        assert rates == sorted(rates)


@pytest.mark.parametrize("year", YEARS)
def test_ordinary_brackets_use_the_seven_federal_rates(year: int) -> None:
    expected = [Decimal(r) for r in ("0.10", "0.12", "0.22", "0.24", "0.32", "0.35", "0.37")]
    for brackets in load_tax_year(year).ordinary_brackets.by_filing_status.values():
        assert [b.rate for b in brackets] == expected


@pytest.mark.parametrize("year", YEARS)
def test_all_money_values_are_int_cents(year: int) -> None:
    checked = 0
    for path, key, value in _walk(_raw(year)):
        if not key.endswith("_cents"):
            continue
        values = value.values() if isinstance(value, dict) else [value]
        for v in values:
            assert v is None or (isinstance(v, int) and not isinstance(v, bool)), f"{path}.{key}"
            checked += 1
    assert checked > 50


@pytest.mark.parametrize("year", YEARS)
def test_no_floats_outside_rate_fields(year: int) -> None:
    for path, key, value in _walk(_raw(year)):
        if isinstance(value, float):
            assert key == "rate" or key.endswith("_rate") or "agi_limits" in path, f"{path}.{key}"


@pytest.mark.parametrize("year", YEARS)
def test_every_referenced_source_exists_and_every_section_has_one(year: int) -> None:
    data = load_tax_year(year)
    known = {s.id for s in data.sources}
    sections = data.sections()
    assert len(sections) == 13
    for name, section in sections.items():
        assert section.source_ids, name
        assert set(section.source_ids) <= known, name


@pytest.mark.parametrize("year", YEARS)
def test_nulls_are_explained(year: int) -> None:
    """A null figure must come with a note saying why (not applicable or unverified)."""
    data = load_tax_year(year)
    for name, section in data.sections().items():
        has_null = any(value is None for key, value in section if key != "note")
        if has_null:
            assert section.note, f"{name} has a null value but no note"


def test_unknown_source_id_is_rejected() -> None:
    raw = _raw(2026)
    raw["hsa"]["source_ids"] = ["no-such-source"]
    with pytest.raises(ValidationError, match="unknown source ids"):
        TaxYearData.model_validate(raw)


def test_float_money_is_rejected() -> None:
    raw = _raw(2026)
    raw["hsa"]["family_cents"] = 875000.5
    with pytest.raises(ValidationError):
        TaxYearData.model_validate(raw)


def test_unsorted_brackets_are_rejected() -> None:
    raw = _raw(2026)
    single = raw["ordinary_brackets"]["by_filing_status"]["single"]
    single[0]["up_to_cents"], single[1]["up_to_cents"] = (
        single[1]["up_to_cents"],
        single[0]["up_to_cents"],
    )
    with pytest.raises(ValidationError, match="ascending"):
        TaxYearData.model_validate(raw)


@pytest.mark.parametrize("year", [1999, 2024, 2030])
def test_unsupported_year_raises(year: int) -> None:
    with pytest.raises(UnsupportedTaxYearError, match=f"No tax data for {year}") as exc:
        load_tax_year(year)
    assert "2025" in str(exc.value) and "2026" in str(exc.value)
    assert isinstance(exc.value, ValueError)


# Spot checks against the primary sources cited in each file.
@pytest.mark.parametrize(
    ("year", "getter", "expected"),
    [
        # Standard deduction (OBBBA-amended for 2025: Rev. Proc. 2025-32 sec. 3.01)
        (2025, lambda d: d.standard_deduction.basic_cents.single, 1_575_000),
        (2025, lambda d: d.standard_deduction.basic_cents.married_filing_jointly, 3_150_000),
        (2025, lambda d: d.standard_deduction.basic_cents.head_of_household, 2_362_500),
        (2026, lambda d: d.standard_deduction.basic_cents.single, 1_610_000),
        (2026, lambda d: d.standard_deduction.basic_cents.married_filing_jointly, 3_220_000),
        (2026, lambda d: d.standard_deduction.basic_cents.head_of_household, 2_415_000),
        (2026, lambda d: d.standard_deduction.additional_age_65_or_blind_cents.unmarried, 205_000),
        # Top of the 12% bracket and start of 37% (single)
        (2025, lambda d: d.ordinary_brackets.by_filing_status["single"][1].up_to_cents, 4_847_500),
        (2026, lambda d: d.ordinary_brackets.by_filing_status["single"][5].up_to_cents, 64_060_000),
        # 0% long-term capital gains ceiling, married filing jointly
        (
            2025,
            lambda d: (
                d.capital_gains_brackets.by_filing_status["married_filing_jointly"][0].up_to_cents
            ),
            9_670_000,
        ),
        (
            2026,
            lambda d: (
                d.capital_gains_brackets.by_filing_status["married_filing_jointly"][0].up_to_cents
            ),
            9_890_000,
        ),
        # SALT cap (OBBBA)
        (2025, lambda d: d.salt_cap.cap_cents, 4_000_000),
        (2026, lambda d: d.salt_cap.cap_cents, 4_040_000),
        (2026, lambda d: d.salt_cap.magi_phaseout_start_cents, 50_500_000),
        # Charitable: non-itemizer deduction and 0.5% floor start in 2026
        (2025, lambda d: d.charitable.non_itemizer_deduction_cents, None),
        (2025, lambda d: d.charitable.itemized_agi_floor_rate, None),
        (2026, lambda d: d.charitable.non_itemizer_deduction_cents.married_filing_jointly, 200_000),
        (2026, lambda d: d.charitable.non_itemizer_deduction_cents.single, 100_000),
        (2026, lambda d: d.charitable.itemized_agi_floor_rate, Decimal("0.005")),
        (2026, lambda d: d.charitable.agi_limits.cash_to_50_percent_orgs, Decimal("0.60")),
        (2026, lambda d: d.charitable.written_acknowledgment_threshold_cents, 25_000),
        # HSA, retirement, FICA
        (2025, lambda d: d.hsa.family_cents, 855_000),
        (2026, lambda d: d.hsa.self_only_cents, 440_000),
        (2025, lambda d: d.retirement.elective_deferral_401k_cents, 2_350_000),
        (2026, lambda d: d.retirement.elective_deferral_401k_cents, 2_450_000),
        (2026, lambda d: d.retirement.ira_cents, 750_000),
        (2026, lambda d: d.retirement.ira_catch_up_50_plus_cents, 110_000),
        (2025, lambda d: d.fica.social_security_wage_base_cents, 17_610_000),
        (2026, lambda d: d.fica.social_security_wage_base_cents, 18_450_000),
        (2026, lambda d: d.fica.medicare_rate, Decimal("0.0145")),
    ],
)
def test_spot_check_verified_figures(year: int, getter, expected) -> None:
    assert getter(load_tax_year(year)) == expected


def test_for_status_lookup() -> None:
    basic = load_tax_year(2026).standard_deduction.basic_cents
    assert basic.for_status("head_of_household") == 2_415_000
    with pytest.raises(ValueError, match="Unknown filing status"):
        basic.for_status("qualifying_widow")
