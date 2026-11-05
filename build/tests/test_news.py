"""Run: python -m unittest discover build/tests"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import news_watch as N  # noqa: E402


def cr(claim, verdict, date="2026-11-01", lang="en", seen=()):
    return {"@type": "ClaimReview", "claimReviewed": claim, "datePublished": date, "inLanguage": lang,
            "url": "https://checker.example/fc/1", "author": {"name": "Checker"},
            "reviewRating": {"alternateName": verdict},
            "itemReviewed": {"appearance": [{"url": u} for u in seen]}}


class FactChecks(unittest.TestCase):
    def parse(self, *items, since="2026-10-01"):
        return N.parse_claimreviews({"dataFeedElement": [{"item": list(items)}]}, since)

    def test_keeps_false_drops_true_old_and_foreign(self):
        got = self.parse(cr("Vaccines contain microchips", "False"),
                         cr("The sky is blue", "True"),
                         cr("Old claim here", "False", date="2025-01-01"),
                         cr("Afirmación falsa", "Falso", lang="es"))
        self.assertEqual([f["claim"] for f in got], ["Vaccines contain microchips"])

    def test_outlet_leads_skip_social_and_checkers(self):
        fcs = self.parse(cr("A false claim", "Mostly false", seen=[
            "https://www.facebook.com/x/posts/1", "https://t.me/chan/2", "https://www.dailymail.co.uk/news/a.html",
            "https://smallblog.example/post", "https://www.awesomescreenshot.com/image/1",
            "https://transcripts.cnn.com/show/x", "https://www.cbsnews.com/news/face-the-nation-transcript-08-23/", "https://checker.example/wp-content/uploads/a.png"]))
        hits = N.outlet_hits(fcs, [{"domain": "dailymail.co.uk", "name": "Daily Mail", "page": "https://x"}])
        self.assertEqual(sorted(h["domain"] for h in hits), ["dailymail.co.uk", "smallblog.example"])
        self.assertTrue(next(h for h in hits if h["domain"] == "dailymail.co.uk")["known"])


    def test_future_dates_dropped(self):
        self.assertEqual(self.parse(cr("Typo year claim", "False", date="2923-01-02")), [])

    def test_public_list_is_science_and_capped(self):
        fcs = self.parse(*[cr(f"Vaccine claim {i}", "False") for i in range(6)], cr("A politician said a thing", "False"))
        pub = N.public_checks(fcs)
        self.assertEqual(len(pub), 4)
        self.assertTrue(all("Vaccine" in f["claim"] for f in pub))


class Papers(unittest.TestCase):
    def test_title_query(self):
        self.assertEqual(N.title_query("RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children"),
                         '"Ileal-lymphoid-nodular hyperplasia non-specific colitis and pervasive developmental disorder"')
        self.assertIsNone(N.title_query("A short title"))

    def test_judge(self):
        item = {"doi": "10.1/abc", "paper": "Coffee cures every known disease in adult mice"}
        said, _ = N.judge(item, ("A new study, Coffee cures every known disease in adult mice, found wonders.", []))
        self.assertEqual(said, "no mention")
        said, _ = N.judge(item, ("The paper Coffee cures every known disease in adult mice was later retracted.", []))
        self.assertEqual(said, "mentions retraction")
        said, _ = N.judge(item, ("Nothing about it here at all.", ["https://doi.org/10.1/abc"]))
        self.assertEqual(said, "no mention")
        self.assertEqual(N.judge(item, ("Unrelated text.", []))[0], None)

    def test_merge_keeps_reviews(self):
        prev = {"items": [{"key": "paper|10.1/a|https://n/1", "kind": "paper", "doi": "10.1/a", "url": "https://n/1",
                           "review": "confirmed", "note": "checked", "first": "2026-10-01"}]}
        items = N.merge(prev, [{"kind": "paper", "doi": "10.1/a", "url": "https://n/1"},
                               {"kind": "paper", "doi": "10.1/b", "url": "https://n/2"}])
        by = {i["key"]: i for i in items}
        self.assertEqual(by["paper|10.1/a|https://n/1"]["review"], "confirmed")
        self.assertEqual(by["paper|10.1/a|https://n/1"]["first"], "2026-10-01")
        self.assertEqual(by["paper|10.1/b|https://n/2"]["review"], "unreviewed")


if __name__ == "__main__":
    unittest.main()
