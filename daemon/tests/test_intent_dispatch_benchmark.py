from benchmarks.intent_dispatch_suite import CASES, benchmark


def test_intent_dispatch_regression_corpus_is_complete() -> None:
    report = benchmark()

    assert len(CASES) >= 50
    assert report["case_count"] == len(CASES)
    assert report["failed"] == 0, report["failures"]
    assert report["accuracy"] == 1.0
