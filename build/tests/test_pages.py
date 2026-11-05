"""Case pages, Results, feed and sitemap (build/site_extras.py)."""
import os, sys, unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import site_extras as X  # noqa: E402
import make_pages as P  # noqa: E402


class Slugs(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(X.slugify("RETRACTED: Gate‐induced Superconductivity in Café (Pub 3)"), "retracted-gate-induced-superconductivity-in-cafe-pub-3")
        s = X.slugify("word " * 40)
        self.assertLessEqual(len(s), 64)
        self.assertFalse(s.endswith("-"))

    def test_slugs_are_stable_and_unique(self):
        M = X.model()
        slugs = [c["slug"] for c in M["cases"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for doi, s in X.load()[3].items():  # every slug on file is kept
            self.assertEqual(M["slugs"][doi], s)


class Said(unittest.TestCase):
    def test_list_sections_and_markup_dropped(self):
        self.assertEqual(X.said({"page": "A", "section": "References", "said": "one two three four five six seven eight nine"}), "")
        self.assertEqual(X.said({"page": "A", "section": "Lead", "said": "see [[link]] one two three four five six seven"}), "")
        s = "Trazodone is used off label for anxiety and the evidence for that is limited."
        self.assertEqual(X.said({"page": "A", "section": "Use", "said": s}), s)


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = P.build()
        cls.M = X.model()

    def test_dismissed_case_is_not_a_fix(self):
        R = X.results_numbers(self.M)
        self.assertTrue(all(x["n"] is None or x["n"].get("status") != "dismissed" for x in R["fixed"]))

    def test_every_case_has_a_page_with_meta(self):
        for c in self.M["cases"]:
            page = self.out[os.path.join(X.ROOT, "case", c["slug"], "index.html")]
            self.assertIn(f'<link rel="canonical" href="{c["url"]}">', page)
            self.assertIn('application/ld+json', page)
            self.assertIn("og:image", page)

    def test_feed_and_sitemap_parse(self):
        feed = ET.fromstring(self.out[os.path.join(X.ROOT, "feed.xml")])
        self.assertTrue(feed.findall("{http://www.w3.org/2005/Atom}entry"))
        ids = [e.find("{http://www.w3.org/2005/Atom}id").text for e in feed.findall("{http://www.w3.org/2005/Atom}entry")]
        self.assertEqual(len(ids), len(set(ids)))
        sm = ET.fromstring(self.out[os.path.join(X.ROOT, "sitemap.xml")])
        self.assertGreater(len(sm), len(self.M["cases"]))

    def test_results_zero_state(self):
        body = X.results_body(self.M)
        self.assertIn("Results", body)
        self.assertNotIn("None", body)


if __name__ == "__main__":
    unittest.main()
