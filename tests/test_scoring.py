"""Unit tests for the scoring engine (pure functions).

Run with:  python3 -m unittest discover -s tests
These use the stdlib ``unittest`` so there is no test dependency to install.
"""

import unittest
from datetime import datetime, timedelta, timezone

from gigradar.config import Config
from gigradar.models import JobPosting
from gigradar.scoring import (
    contract_score,
    extract_hourly_rate,
    quality_score,
    rate_score,
    recency_score,
    red_flag_score,
    score_posting,
    stack_match_score,
)


def make_posting(**kw) -> JobPosting:
    base = dict(
        source="test",
        external_id="1",
        title="Job",
        company="ACME",
        url="https://example.com/1",
        description="",
        tags=[],
    )
    base.update(kw)
    return JobPosting(**base)


class StackMatchTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config().normalized()

    def test_no_match_scores_zero(self):
        p = make_posting(title="Underwater basket weaving", description="nothing here")
        score, reasons = stack_match_score(p, self.cfg)
        self.assertEqual(score, 0.0)
        self.assertEqual(reasons, [])

    def test_single_match(self):
        p = make_posting(description="We need a Python developer")
        score, reasons = stack_match_score(p, self.cfg)
        self.assertAlmostEqual(score, 0.5, places=5)
        self.assertTrue(any("python" in r for r in reasons))

    def test_more_matches_score_higher_with_saturation(self):
        p1 = make_posting(description="python")
        p2 = make_posting(description="python aws terraform")
        s1, _ = stack_match_score(p1, self.cfg)
        s2, _ = stack_match_score(p2, self.cfg)
        self.assertGreater(s2, s1)
        self.assertLessEqual(s2, 1.0)

    def test_empty_stack_is_safe(self):
        cfg = Config(stack=[]).normalized()
        p = make_posting(description="python aws")
        score, _ = stack_match_score(p, cfg)
        self.assertEqual(score, 0.0)


class RateParsingTests(unittest.TestCase):
    def test_extract_simple_hourly(self):
        self.assertEqual(extract_hourly_rate("Pay is $75/hr"), 75.0)

    def test_extract_per_hour_phrase(self):
        self.assertEqual(extract_hourly_rate("80 per hour"), 80.0)

    def test_extract_range_takes_higher(self):
        self.assertEqual(extract_hourly_rate("$60-$90/hr"), 90.0)

    def test_extract_none_when_absent(self):
        self.assertIsNone(extract_hourly_rate("great opportunity, competitive pay"))


class RateScoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(min_hourly_rate=50.0).normalized()

    def test_unknown_pay_is_neutral(self):
        p = make_posting(description="no pay mentioned", rate_type="")
        score, reasons = rate_score(p, self.cfg)
        self.assertEqual(score, 0.5)
        self.assertIn("pay not stated", reasons)

    def test_structured_annual_converts_to_hourly(self):
        p = make_posting(rate_type="annual", salary_max=208000.0)
        score, _ = rate_score(p, self.cfg)
        # 208000/2080 = $100/hr; floor*2 = 100 -> score 1.0
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_low_text_rate_scores_below_half(self):
        p = make_posting(description="budget is $25/hr")
        score, _ = rate_score(p, self.cfg)
        self.assertLess(score, 0.5)

    def test_high_text_rate_scores_high(self):
        p = make_posting(description="paying $100/hr for this")
        score, _ = rate_score(p, self.cfg)
        self.assertAlmostEqual(score, 1.0, places=5)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config().normalized()

    def test_signals_increase_score(self):
        p = make_posting(description="clear scope with milestone and budget")
        score, reasons = quality_score(p, self.cfg)
        self.assertGreater(score, 0.0)
        self.assertTrue(reasons)

    def test_long_description_bonus(self):
        p = make_posting(description="x" * 500)
        score, reasons = quality_score(p, self.cfg)
        self.assertGreaterEqual(score, 0.2)
        self.assertIn("detailed description", reasons)


class RecencyTests(unittest.TestCase):
    def test_today_scores_near_one(self):
        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        p = make_posting(posted_at=now)
        score, _ = recency_score(p, now=now)
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_old_posting_decays(self):
        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        p = make_posting(posted_at=now - timedelta(days=7))
        score, _ = recency_score(p, now=now)
        self.assertAlmostEqual(score, 0.5, places=5)

    def test_beyond_window_is_zero(self):
        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        p = make_posting(posted_at=now - timedelta(days=30))
        score, _ = recency_score(p, now=now)
        self.assertEqual(score, 0.0)

    def test_missing_date_is_neutral(self):
        p = make_posting(posted_at=None)
        score, _ = recency_score(p)
        self.assertEqual(score, 0.5)


class RedFlagTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config().normalized()

    def test_clean_posting_no_penalty(self):
        p = make_posting(description="well scoped python contract")
        mag, reasons = red_flag_score(p, self.cfg)
        self.assertEqual(mag, 0.0)
        self.assertEqual(reasons, [])

    def test_flags_produce_penalty(self):
        p = make_posting(description="need a rockstar ninja to build everything, unpaid")
        mag, reasons = red_flag_score(p, self.cfg)
        self.assertGreater(mag, 0.0)
        self.assertTrue(reasons)


class ContractScoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config().normalized()

    def test_freelance_language_scores_high(self):
        p = make_posting(
            title="Freelance React contractor",
            description="Short-term project-based contract, hourly rate.",
        )
        score, reasons = contract_score(p, self.cfg)
        self.assertGreater(score, 0.6)
        self.assertTrue(any("contract" in r for r in reasons))

    def test_fulltime_language_scores_low(self):
        p = make_posting(
            title="Senior Engineer (Full-time)",
            description="Permanent W-2 employee, 401k, benefits package, PTO.",
        )
        score, reasons = contract_score(p, self.cfg)
        self.assertLess(score, 0.3)
        self.assertTrue(any("full-time" in r for r in reasons))

    def test_neutral_when_undetermined(self):
        p = make_posting(title="Developer", description="We build software.")
        score, _ = contract_score(p, self.cfg)
        self.assertAlmostEqual(score, 0.3, places=5)

    def test_freelance_beats_fulltime(self):
        gig = make_posting(description="freelance hourly contract gig")
        fte = make_posting(description="full-time permanent employee with benefits 401k")
        s_gig, _ = contract_score(gig, self.cfg)
        s_fte, _ = contract_score(fte, self.cfg)
        self.assertGreater(s_gig, s_fte)


class EndToEndScoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(min_hourly_rate=50.0).normalized()
        self.now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    def test_great_gig_beats_bad_gig(self):
        good = make_posting(
            title="Senior Python / AWS Terraform freelance contractor",
            description=("Detailed scope with milestones and budget. "
                         "Freelance contract, paying $100/hr for a well-defined "
                         "backend API project. " + "More context. " * 40),
            posted_at=self.now,
        )
        bad = make_posting(
            title="Rockstar ninja wanted",
            description="build everything, unpaid, equity only, urgent urgent",
            posted_at=self.now - timedelta(days=20),
        )
        score_posting(good, self.cfg, now=self.now)
        score_posting(bad, self.cfg, now=self.now)
        self.assertGreater(good.score, bad.score)
        self.assertGreaterEqual(good.score, 70.0)
        self.assertLessEqual(bad.score, 20.0)

    def test_score_is_clamped_0_100(self):
        p = make_posting(
            title="python aws terraform java cloud devops kubernetes",
            description="python aws terraform scope milestone budget $200/hr " * 5,
            posted_at=self.now,
        )
        score_posting(p, self.cfg, now=self.now)
        self.assertLessEqual(p.score, 100.0)
        self.assertGreaterEqual(p.score, 0.0)


if __name__ == "__main__":
    unittest.main()
