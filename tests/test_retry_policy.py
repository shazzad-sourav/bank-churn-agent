"""Rate-limit handling: per-minute limits are retried, a used-up daily quota goes to the fallback."""
from churn_agent.agent import _is_transient, is_daily_quota

PER_MINUTE = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, "
              "quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier. Please retry in 20s.")
PER_DAY = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, "
           "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")


def test_per_minute_limit_is_retried():
    assert _is_transient(Exception(PER_MINUTE))
    assert not is_daily_quota(PER_MINUTE)


def test_daily_quota_is_not_retried():
    assert is_daily_quota(PER_DAY)
    assert not _is_transient(Exception(PER_DAY))


def test_outage_is_retried_and_bad_model_is_not():
    assert _is_transient(Exception("503 UNAVAILABLE: The model is overloaded"))
    assert not _is_transient(Exception("404 NOT_FOUND: models/gemini-9-flash is not found"))
