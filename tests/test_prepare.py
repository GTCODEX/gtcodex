"""
Tests for the dataset builder (football_stats.prepare).

Run from the repository root:

    python -m unittest tests.test_prepare -v
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from football_stats import data as d
from football_stats import prepare


OPENMATCHDAY_HEADER = (
    "gw,date,time,home,away,ft_home,ft_away,ft_result,ht_home,ht_away,ht_result,"
    "home_shots,away_shots,home_target,away_target,home_fouls,away_fouls,"
    "home_corners,away_corners,home_corners_1h,away_corners_1h,"
    "home_corners_2h,away_corners_2h,home_yellow,away_yellow,home_red,away_red,"
    "goal_minutes,source"
)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header.split(","))
        w.writerows(rows)


class TestBuild202627(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.raw = self.dir / "results_2627.csv"
        write_csv(self.raw, OPENMATCHDAY_HEADER, [
            ["1", "2026-08-21", "20:00", "Arsenal", "Coventry", "3", "0", "H",
             "2", "0", "H", "20", "4", "6", "1", "10", "13", "8", "2", "5", "1",
             "3", "1", "1", "1", "0", "0", "15,23,49", "fixturedl"],
            ["1", "2026-08-22", "12:30", "Hull", "Man Utd", "", "", "", "", "", "",
             "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "fixturedl"],
            ["2", "2026-08-29", "15:00", "Man City", "Spurs", "2", "2", "D",
             "1", "1", "D", "18", "9", "7", "3", "8", "11", "6", "4", "", "", "",
             "", "2", "2", "0", "1", "12,45", "fixturedl"],
        ])
        self.out = self.dir / "epl_2026_27.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_played_matches_are_kept(self):
        n = prepare.build_epl_2026_27(self.raw, self.out,
                                     supplement=self.dir / "none.csv")
        self.assertEqual(n, 2)

    def test_columns_and_canonical_names(self):
        prepare.build_epl_2026_27(self.raw, self.out,
                                  supplement=self.dir / "none.csv")
        rows = list(csv.DictReader(open(self.out, encoding="utf-8")))
        self.assertEqual(rows[0]["home"], "Arsenal")
        self.assertEqual(rows[0]["away"], "Coventry City")
        self.assertEqual(rows[1]["home"], "Manchester City")
        self.assertEqual(rows[1]["away"], "Tottenham Hotspur")
        self.assertEqual(rows[0]["round"], "Matchday 1")
        self.assertEqual(rows[0]["home_shots_on_target"], "6")
        self.assertEqual(rows[1]["home_corners"], "6")
        self.assertEqual(rows[1]["goal_minutes"], "12,45")

    def test_output_loads_through_the_data_layer(self):
        prepare.build_epl_2026_27(self.raw, self.out,
                                  supplement=self.dir / "none.csv")
        matches = d.load_csv(self.out)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].result, "H")
        self.assertEqual(matches[1].result, "D")
        self.assertEqual(matches[0].stat("home_shots"), 20.0)
        self.assertEqual(matches[1].stat("home_shots"), 18.0)
        self.assertEqual(matches[1].stat("ht_home_goals"), 1.0)


class TestSupplement(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.raw = self.dir / "results_2627.csv"
        write_csv(self.raw, OPENMATCHDAY_HEADER, [
            ["11", "2026-11-22", "15:00", "Hull", "Brighton", "2", "0", "H",
             "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
             "", "", "92,95", "fixturedl"],
        ])
        self.sup = self.dir / "supplement.csv"
        write_csv(self.sup, "date,home,away,home_goals,away_goals,note", [
            ["2026-11-22", "Liverpool", "Manchester United", "4", "0", "played"],
            ["2026-11-22", "Hull", "Brighton", "9", "9", "duplicate, ignored"],
        ])
        self.out = self.dir / "epl_2026_27.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_supplement_is_merged_and_duplicates_skipped(self):
        rows = prepare._read_supplement(
            self.sup, {"Hull City|Brighton & Hove Albion"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home"], "Liverpool")
        self.assertEqual(rows[0]["result"], "H")

    def test_builder_includes_the_supplement(self):
        n = prepare.build_epl_2026_27(self.raw, self.out, supplement=self.sup)
        self.assertEqual(n, 2)
        rows = list(csv.DictReader(open(self.out, encoding="utf-8")))
        self.assertEqual({r["home"] for r in rows}, {"Hull City", "Liverpool"})


class TestBuild202526(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.raw = self.dir / "results.csv"
        write_csv(self.raw,
                  "match_id,season,date,home_team,away_team,fthg,ftag,ftr,hthg,htag,htr",
                  [["1", "2024-25", "2024-08-17", "Arsenal", "Wolves", "2", "0", "H", "1", "0", "H"],
                   ["2", "2025-26", "2025-08-15", "Liverpool", "Bournemouth", "4", "2", "H", "1", "0", "H"],
                   ["3", "2025-26", "2025-08-16", "Man United", "West Ham", "1", "1", "D", "0", "0", "D"]])
        self.out = self.dir / "epl_2025_26.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_filters_to_the_requested_season(self):
        n = prepare.build_epl_2025_26(self.raw, self.out)
        self.assertEqual(n, 2)
        rows = list(csv.DictReader(open(self.out, encoding="utf-8")))
        self.assertEqual({r["home"] for r in rows}, {"Liverpool", "Manchester United"})

    def test_rounds_are_labelled_in_blocks_of_ten(self):
        prepare.build_epl_2025_26(self.raw, self.out)
        rows = list(csv.DictReader(open(self.out, encoding="utf-8")))
        self.assertTrue(all(r["round"].startswith("Matchday ") for r in rows))

    def test_half_time_columns_are_kept(self):
        prepare.build_epl_2025_26(self.raw, self.out)
        rows = list(csv.DictReader(open(self.out, encoding="utf-8")))
        self.assertEqual(rows[0]["ht_home_goals"], "1")
        self.assertEqual(rows[0]["ht_result"], "H")


class TestBundledDatasets(unittest.TestCase):
    """The committed CSVs must be the ones the builder produces."""

    def test_recent_season_is_current(self):
        matches = d.load_dataset("epl_2026_27")
        self.assertGreaterEqual(len(matches), 100)
        self.assertGreaterEqual(matches[-1].date, "2026-11-01")

    def test_previous_season_is_complete(self):
        matches = d.load_dataset("epl_2025_26")
        self.assertEqual(len(matches), 380)

    def test_composite_dataset(self):
        recent = d.load_dataset("epl_recent")
        self.assertEqual(len(recent), 380 + len(d.load_dataset("epl_2026_27")))
        self.assertEqual(len(d.team_names(recent)), 23)
        self.assertLessEqual(recent[0].date, recent[-1].date)

    def test_dataset_ids_and_labels(self):
        ids = d.dataset_ids()
        self.assertIn("epl_recent", ids)
        self.assertEqual(d.dataset_label("epl_2018_19"), "2018/19")
        self.assertIn("recent", d.dataset_label("epl_recent"))
        self.assertTrue(d.is_composite("epl_recent"))
        self.assertFalse(d.is_composite("epl_2018_19"))

    def test_unknown_dataset_raises(self):
        with self.assertRaises(KeyError):
            d.load_dataset("epl_1999_00")

    def test_missing_stat_cells_are_not_zero(self):
        m = d.Match(date="2026-01-01", home="A", away="B", home_goals=1, away_goals=0,
                    stats={"home_shots": ""})
        self.assertEqual(m.stat("home_shots"), 0.0)
        self.assertEqual(m.stat("home_shots", 7.0), 7.0)


if __name__ == "__main__":
    unittest.main()
