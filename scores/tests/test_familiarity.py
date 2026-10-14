"""Tests for word familiarity, the De-Jargonizer bands and burden weights."""

from __future__ import annotations

import math

import pytest

from rbscores.familiarity import (
    FAMILIAR_ZIPF,
    JARGON_COMMON_ABOVE_ZIPF,
    JARGON_RARE_BELOW_ZIPF,
    UNKNOWN_ZIPF,
    JargonBand,
    WordfreqFamiliarity,
    jargon_band,
    unfamiliarity,
)


def test_dejargonizer_cutoffs_match_the_published_counts() -> None:
    """50 and 1,000 occurrences in 90M words convert to Zipf 2.74 and 4.05."""
    rare, common = JARGON_RARE_BELOW_ZIPF, JARGON_COMMON_ABOVE_ZIPF
    assert rare == pytest.approx(math.log10(50 / 90e6 * 1e9))
    assert rare == pytest.approx(2.745, abs=0.001)
    assert common == pytest.approx(4.046, abs=0.001)


@pytest.mark.parametrize(
    ("zipf", "band"),
    [
        (7.0, JargonBand.COMMON),
        (4.1, JargonBand.COMMON),
        (4.0, JargonBand.MID),
        (2.75, JargonBand.MID),
        (2.7, JargonBand.RARE),
        (0.0, JargonBand.RARE),
    ],
)
def test_jargon_band_boundaries(zipf: float, band: JargonBand) -> None:
    """Zipf values fall into the band their thresholds say."""
    assert jargon_band(zipf) is band


def test_unfamiliarity_is_zero_for_familiar_one_for_unknown_and_linear_between() -> None:
    """The weight is clipped to [0, 1] and linear between the anchors."""
    assert unfamiliarity(FAMILIAR_ZIPF) == 0.0
    assert unfamiliarity(7.0) == 0.0
    assert unfamiliarity(UNKNOWN_ZIPF) == 1.0
    assert unfamiliarity(0.0) == 1.0
    midpoint = (FAMILIAR_ZIPF + UNKNOWN_ZIPF) / 2
    assert unfamiliarity(midpoint) == pytest.approx(0.5)


def test_wordfreq_orders_common_words_above_technical_ones(
    wordfreq_familiarity: WordfreqFamiliarity,
) -> None:
    """Real wordfreq data: everyday words are more frequent than jargon."""
    assert wordfreq_familiarity.zipf("the") > 7
    assert wordfreq_familiarity.zipf("kidney") > wordfreq_familiarity.zipf("nephron")
    assert wordfreq_familiarity.zipf("Protein") == wordfreq_familiarity.zipf("protein")
    assert wordfreq_familiarity.zipf("qwxzzvq") == 0.0


def test_letter_digit_codes_use_their_letters_or_count_as_unseen(
    wordfreq_familiarity: WordfreqFamiliarity,
) -> None:
    """IL-6 has too few letters to look up; COVID-19 is looked up as "covid"."""
    assert wordfreq_familiarity.zipf("IL-6") == 0.0
    assert wordfreq_familiarity.zipf("PRC2") == wordfreq_familiarity.zipf("prc")
    assert wordfreq_familiarity.zipf("COVID-19") == wordfreq_familiarity.zipf("covid")
