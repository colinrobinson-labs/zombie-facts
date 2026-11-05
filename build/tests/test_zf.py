"""Run: python -m unittest discover build/tests"""
import copy, json, os, sys, unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import build_data as B  # noqa: E402
import recheck as R  # noqa: E402

DATA = os.path.join(HERE, "..", "..", "data.json")


def paper(doi, pages, status="zombie", authors=("Ann Lee",)):
    return {"doi": doi, "title": "T " + doi, "authors": list(authors), "retracted": "2020-01-01",
            "wiki": [{"page": p, "status": status, "views": 100, "said": "x", "section": "Lead"} for p in pages]}


class Ledger(unittest.TestCase):
    def setUp(self):
        self.ps = [paper("10.1/a", ["A", "B"]), paper("10.1/b", ["C"])]
        self.hits = {"10.1/a": {"A", "B"}, "10.1/b": {"C"}}
        self.pages = {t: {"text": "x"} for t in "ABC"}
        self.L = B.update_ledger({}, self.ps, self.hits, self.pages, "2026-11-05")

    def test_opens_every_zombie(self):
        self.assertEqual(len(self.L["cases"]), 3)
        self.assertTrue(all(c["o"] == "2026-11-05" and not c["c"] for c in self.L["cases"].values()))

    def test_flagged_and_removed_close(self):
        ps = copy.deepcopy(self.ps)
        ps[0]["wiki"][0]["status"] = "flagged"
        hits = {"10.1/a": {"A", "B"}, "10.1/b": set()}
        ps[1]["wiki"] = []
        L2 = B.update_ledger({"ledger": self.L}, ps, hits, self.pages, "2026-11-12")
        self.assertEqual(L2["cases"]["10.1/a|A"]["how"], "flagged")
        self.assertEqual(L2["cases"]["10.1/b|C"]["how"], "removed")
        self.assertIsNone(L2["cases"]["10.1/a|B"]["c"])
        self.assertIsNone(self.L["cases"]["10.1/a|A"]["c"], "previous ledger must not be mutated")

    def test_unread_page_stays_open(self):
        ps = copy.deepcopy(self.ps); ps[1]["wiki"] = []
        pages = {"A": {"text": "x"}, "B": {"text": "x"}}
        L2 = B.update_ledger({"ledger": self.L}, ps, self.hits, pages, "2026-11-12")
        self.assertIsNone(L2["cases"]["10.1/b|C"]["c"])

    def test_mass_close_guard(self):
        many = [paper(f"10.1/{i}", ["P%d" % i]) for i in range(30)]
        L = B.update_ledger({}, many, {}, {}, "2026-11-05")
        L2 = B.update_ledger({"ledger": L}, [], {}, {}, "2026-11-12")
        self.assertFalse(any(c["c"] for c in L2["cases"].values()))

    def test_reopen(self):
        ps = copy.deepcopy(self.ps); ps[0]["wiki"][0]["status"] = "flagged"
        L2 = B.update_ledger({"ledger": self.L}, ps, self.hits, self.pages, "2026-11-12")
        L3 = B.update_ledger({"ledger": L2}, self.ps, self.hits, self.pages, "2026-11-19")
        self.assertIsNone(L3["cases"]["10.1/a|A"]["c"])
        self.assertEqual(L3["cases"]["10.1/a|A"]["re"], 1)


class Classify(unittest.TestCase):
    def test_author_page(self):
        self.assertTrue(B.is_author_page("Bruce Gilley", ["Bruce Gilley"]))
        self.assertTrue(B.is_author_page("John Smith (biologist)", ["John A. Smith"]))
        self.assertFalse(B.is_author_page("Trazodone", ["John Smith"]))
        self.assertFalse(B.is_author_page("Smith", ["John Smith"]))

    def test_flag_detection(self):
        txt = "Claim here.<ref>{{cite journal |doi=10.1/zz |title=X}} {{Retracted|doi=10.1/zz}}</ref> More."
        low = txt.lower()
        _, _, fl = B.context_for(txt, low, low.find("10.1/zz"))
        self.assertTrue(fl)
        txt2 = "Claim here.<ref>{{cite journal |doi=10.1/zz |title=X}}</ref> More."
        _, _, fl2 = B.context_for(txt2, txt2.lower(), txt2.lower().find("10.1/zz"))
        self.assertFalse(fl2)


class Talk(unittest.TestCase):
    TXT = """== Older ==
Hi. [[User:Someone|Someone]] 10:00, 1 January 2026 (UTC)

== Retracted source cited: Foo ==
The section cites a retracted paper. [[User:ZombieFacts|ZombieFacts]] ([[User talk:ZombieFacts|talk]]) 12:00, 6 November 2026 (UTC)
:Thanks, I've replaced it with the 2020 review. [[User:Editor_One|Editor One]] ([[User talk:Editor One|talk]]) 14:05, 7 November 2026 (UTC)
::Agreed. [[User talk:Two|Two]] 09:30, 8 November 2026 (UTC)

== Next ==
x
"""

    def test_section_and_replies(self):
        body = R.find_section(self.TXT, "Retracted source cited: Foo")
        self.assertIsNotNone(body)
        rs = R.parse_replies(body, ["ZombieFacts"])
        self.assertEqual([r["user"] for r in rs], ["Editor One", "Two"])
        self.assertEqual(rs[0]["at"], "2026-11-07T14:05Z")
        self.assertIn("replaced it", rs[0]["said"])
        self.assertIsNone(R.find_section(self.TXT, "Missing"))


class DataFile(unittest.TestCase):
    def test_shape(self):
        d = json.load(open(DATA))
        for k in ("built", "stats", "papers", "ledger"):
            self.assertIn(k, d)
        self.assertGreater(len(d["papers"]), 50)
        keys = {p["doi"] + "|" + w["page"] for p in d["papers"] for w in p["wiki"] if w["status"] == "zombie"}
        self.assertTrue(keys <= set(d["ledger"]["cases"]), "every zombie citation has a case")
        for p in d["papers"]:
            self.assertTrue(p["doi"].startswith("10."))
            self.assertEqual(p["zombies"], sum(w["status"] == "zombie" for w in p["wiki"]))


if __name__ == "__main__":
    unittest.main()
