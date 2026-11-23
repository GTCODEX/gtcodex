"""
Tests for the forecast log: recording, settling, scoring and the API endpoints.

Run from the repository root:

    python -m unittest tests.test_prediction_log -v
"""
import json
import math
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from football_stats import data as d
from football_stats import prediction_log as plog
from football_stats import predictor as p
import server


def make_prediction(home="Arsenal", away="Chelsea", h=0.6, dr=0.2, a=0.2,
                    over=0.55, btts=0.6):
    return p.Prediction(
        home=home, away=away, home_win=h, draw=dr, away_win=a,
        over_2_5=over, under_2_5=1 - over, btts=btts,
        expected_home_goals=1.5, expected_away_goals=1.0,
        most_likely_score="1-0", most_likely_prob=max(h, dr, a),
        confidence=max(h, dr, a), model_agreement=1.0, source="poisson+elo",
    )


def match(home, away, hg, ag, date="2026-11-22"):
    return d.Match(date=date, home=home, away=away, home_goals=hg, away_goals=ag)


class TempLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "prediction_log.json"

    def tearDown(self):
        self._tmp.cleanup()

    def record(self, *args, **kwargs):
        kwargs.setdefault("path", self.path)
        return plog.record(*args, **kwargs)

    def settle(self, results):
        plog.settle_from_matches(plog.load_log(self.path), results, path=self.path)
        return plog.load_log(self.path)


class TestRecord(TempLog):
    def test_record_appends_and_round_trips(self):
        rec = self.record(make_prediction(), fixture_date="2026-11-22",
                          dataset="epl_recent", odds=(2.1, 3.4, 3.6))
        self.assertTrue(rec.id)
        self.assertEqual(rec.status, "pending")
        self.assertEqual(rec.odds, [2.1, 3.4, 3.6])

        loaded = plog.load_log(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].home, "Arsenal")
        self.assertEqual(loaded[0].dataset, "epl_recent")
        self.assertFalse(loaded[0].settled)

    def test_record_does_not_touch_the_default_log(self):
        before = plog.DEFAULT_LOG_PATH.exists()
        self.record(make_prediction())
        self.assertEqual(plog.DEFAULT_LOG_PATH.exists(), before)

    def test_load_missing_file_is_empty(self):
        self.assertEqual(plog.load_log(self.path), [])

    def test_load_corrupt_file_is_empty(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(plog.load_log(self.path), [])

    def test_most_likely_outcome(self):
        self.assertEqual(make_prediction(h=0.6).most_likely_outcome, "H")
        self.assertEqual(make_prediction(h=0.2, dr=0.5, a=0.3).most_likely_outcome, "D")
        self.assertEqual(make_prediction(h=0.2, dr=0.2, a=0.6).most_likely_outcome, "A")


class TestSettle(TempLog):
    def test_settle_fills_in_the_result(self):
        self.record(make_prediction())
        n = plog.settle_from_matches(plog.load_log(self.path),
                                     [match("Arsenal", "Chelsea", 2, 1)],
                                     path=self.path, dataset_name="epl_2026_27")
        self.assertEqual(n, 1)
        rec = plog.load_log(self.path)[0]
        self.assertEqual(rec.status, "settled")
        self.assertEqual(rec.result, "H")
        self.assertEqual((rec.home_goals, rec.away_goals), (2, 1))
        self.assertEqual(rec.settled_from, "epl_2026_27")

    def test_settle_is_idempotent(self):
        self.record(make_prediction())
        results = [match("Arsenal", "Chelsea", 2, 1)]
        plog.settle_from_matches(plog.load_log(self.path), results,
                                 path=self.path, dataset_name="x")
        n = plog.settle_from_matches(plog.load_log(self.path), results,
                                     path=self.path, dataset_name="x")
        self.assertEqual(n, 0)

    def test_settle_matches_canonical_club_names(self):
        self.record(make_prediction(home="Man Utd", away="Spurs"))
        n = plog.settle_from_matches(
            plog.load_log(self.path),
            [match("Manchester United", "Tottenham Hotspur", 1, 1)],
            path=self.path)
        self.assertEqual(n, 1)
        self.assertEqual(plog.load_log(self.path)[0].result, "D")

    def test_settle_leaves_unplayed_fixtures_pending(self):
        self.record(make_prediction(home="Arsenal", away="Chelsea"))
        self.record(make_prediction(home="Liverpool", away="Everton"))
        n = plog.settle_from_matches(plog.load_log(self.path),
                                     [match("Arsenal", "Chelsea", 1, 0)],
                                     path=self.path)
        self.assertEqual(n, 1)
        statuses = {r.home: r.status for r in plog.load_log(self.path)}
        self.assertEqual(statuses, {"Arsenal": "settled", "Liverpool": "pending"})

    def test_settle_from_datasets_uses_the_bundled_data(self):
        self.record(make_prediction(home="Hull City",
                                    away="Brighton & Hove Albion"))
        n = plog.settle_from_datasets(dataset_ids=["epl_2026_27"], path=self.path,
                                      verbose=False)
        self.assertEqual(n, 1)
        rec = plog.load_log(self.path)[0]
        self.assertEqual(rec.result, "H")
        self.assertEqual((rec.home_goals, rec.away_goals), (2, 0))


class TestScore(TempLog):
    def _settled(self, pred, hg, ag):
        self.record(pred, fixture_date="2026-11-22")
        self.settle([match(pred.home, pred.away, hg, ag)])
        return plog.load_log(self.path)[-1:]

    def test_empty_log_scores_zero(self):
        s = plog.score(plog.load_log(self.path))
        self.assertEqual(s["n"], 0)
        self.assertIsNone(s["accuracy"])
        self.assertIsNone(s["log_loss"])
        self.assertEqual(s["pending"], 0)

    def test_accuracy_and_log_loss(self):
        records = self._settled(make_prediction(h=0.7, dr=0.2, a=0.1), 2, 0) \
            + self._settled(make_prediction(home="Liverpool", away="Everton",
                                            h=0.2, dr=0.2, a=0.6), 2, 0)
        s = plog.score(records)
        self.assertEqual(s["n"], 2)
        self.assertAlmostEqual(s["accuracy"], 0.5)
        self.assertLess(s["accuracy_ci"][0], 0.5)
        self.assertGreater(s["accuracy_ci"][1], 0.5)
        # first pick was H at 0.7 and won; second was A at 0.6 and lost to an H
        self.assertAlmostEqual(s["log_loss"], -(math.log(0.7) + math.log(0.2)) / 2,
                               places=6)

    def test_over_under_and_btts(self):
        # 3-2: over 2.5 and both teams score — both picks right
        s = plog.score(self._settled(make_prediction(over=0.8, btts=0.8), 3, 2))
        self.assertEqual(s["over_under_accuracy"], 1.0)
        self.assertEqual(s["btts_accuracy"], 1.0)

        # 2-0: under 2.5 and only one team scores — both picks wrong
        s = plog.score(self._settled(make_prediction(over=0.8, btts=0.8), 2, 0))
        self.assertEqual(s["over_under_accuracy"], 0.0)
        self.assertEqual(s["btts_accuracy"], 0.0)

        # 2-0 again, this time picking the under and the clean sheet
        s = plog.score(self._settled(make_prediction(over=0.2, btts=0.2), 2, 0))
        self.assertEqual(s["over_under_accuracy"], 1.0)
        self.assertEqual(s["btts_accuracy"], 1.0)

        # 1-1: under, both score
        s = plog.score(self._settled(make_prediction(over=0.2, btts=0.8), 1, 1))
        self.assertEqual(s["over_under_accuracy"], 1.0)
        self.assertEqual(s["btts_accuracy"], 1.0)

    def test_calibration_table(self):
        rows = plog.calibration(self._settled(make_prediction(h=0.9, dr=0.05, a=0.05),
                                              1, 0))
        self.assertEqual(sum(r["n"] for r in rows), 1)
        row = [r for r in rows if r["n"]][0]
        self.assertEqual(row["observed"], 1.0)
        self.assertAlmostEqual(row["mean_pred"], 0.9)

    def test_ece_zero_for_a_certain_correct_pick(self):
        records = self._settled(make_prediction(h=1.0, dr=0.0, a=0.0), 1, 0)
        self.assertAlmostEqual(plog.expected_calibration_error(records), 0.0, places=6)

    def test_ece_nonzero_for_a_certain_wrong_pick(self):
        records = self._settled(make_prediction(h=1.0, dr=0.0, a=0.0), 0, 1)
        self.assertGreater(plog.expected_calibration_error(records), 0.9)

    def test_summary_mentions_the_counts(self):
        self.record(make_prediction())
        text = plog.summary(plog.load_log(self.path))
        self.assertIn("1 records", text)
        self.assertIn("1 awaiting a result", text)


class TestLogEndpoints(unittest.TestCase):
    """The dashboard's forecast-log endpoints, served by the LeadFinder handler."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "prediction_log.json"
        self._old_default = plog.DEFAULT_LOG_PATH
        plog.DEFAULT_LOG_PATH = self.path
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        plog.DEFAULT_LOG_PATH = self._old_default
        self.httpd.shutdown()
        self.httpd.server_close()
        self._tmp.cleanup()

    def _req(self, path, method="GET", payload=None, timeout=120):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_log_endpoint_empty(self):
        code, body = self._req("/api/predictor/log")
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["score"]["n"], 0)
        self.assertEqual(payload["calibration"], plog.calibration([]))

    def test_predict_with_log_flag_records_the_forecast(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19", "home": "Arsenal",
                                        "away": "Chelsea", "log": True})
        self.assertEqual(code, 200)
        log_id = json.loads(body)["log_id"]
        records = plog.load_log(self.path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, log_id)
        self.assertEqual(records[0].status, "pending")

    def test_predict_without_log_flag_writes_nothing(self):
        code, _ = self._req("/api/predictor/predict", method="POST",
                            payload={"dataset": "epl_2018_19", "home": "Arsenal",
                                     "away": "Chelsea"})
        self.assertEqual(code, 200)
        self.assertEqual(plog.load_log(self.path), [])

    def test_settle_endpoint(self):
        plog.record(make_prediction(home="Hull City",
                                    away="Brighton & Hove Albion"), path=self.path)
        code, body = self._req("/api/predictor/log/settle", method="POST", payload={})
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual(payload["settled"], 1)
        self.assertEqual(payload["score"]["n"], 1)

    def test_log_endpoint_reports_a_settled_record(self):
        # Pick the away win; Hull actually won 2-0, so this is a miss.
        plog.record(make_prediction(home="Hull City",
                                    away="Brighton & Hove Albion",
                                    h=0.2, dr=0.2, a=0.6), path=self.path)
        plog.settle_from_datasets(dataset_ids=["epl_2026_27"], path=self.path,
                                  verbose=False)
        code, body = self._req("/api/predictor/log")
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual(payload["records"][0]["result"], "H")
        self.assertEqual(payload["score"]["accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
