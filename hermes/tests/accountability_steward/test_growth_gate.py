"""Unit tests for the accountability-steward growth gate (pure core only)."""
import importlib.util
import os
import subprocess
import unittest

HERE = os.path.dirname(__file__)
GATE = os.path.join(HERE, "../../profiles/accountability-steward/scripts/growth_gate.py")
spec = importlib.util.spec_from_file_location("growth_gate", GATE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

BRANCH = "bot/accountability-steward-20261015"


def f(path, status="M", added=(), removed=()):
    return {"path": path, "status": status, "added": list(added), "removed": list(removed)}


def info(files, target="protocol", **kw):
    base = {"target": target, "branch": BRANCH, "files": files, "age_hours": 48.0,
            "labels": [], "paused": False, "merged_24h": 0,
            "tests": {"ok": True, "head_n": 140, "base_n": 138, "detail": ""},
            "read_base": lambda p: None, "read_head": lambda p: None}
    base.update(kw)
    return base


B_FILES = [f("src/kotoba/protocol/nullifier.cljk", "A", ["(ns kotoba.protocol.nullifier)"]),
           f("test/kotoba/protocol/nullifier_test.cljk", "A", ["(ns x)"]),
           f("test/run_portable.cljk", "M", ["         '[kotoba.protocol.nullifier-test]"], [])]


class Classify(unittest.TestCase):
    def test_docs_only_is_a(self):
        self.assertEqual("A", g.classify([f("docs/x.md", "M", ["a"], ["b"])])[0])

    def test_comment_only_source_is_a(self):
        self.assertEqual("A", g.classify([f("src/a.cljk", "M", [";; new"], [";; old"])])[0])

    def test_code_change_is_not_comment_only(self):
        self.assertEqual("C", g.classify([f("src/a.cljk", "M", ["(def x 1)"], [";; old"])])[0])

    def test_additive_algebra_is_b(self):
        self.assertEqual("B", g.classify(B_FILES)[0])

    def test_modifying_existing_source_is_c(self):
        self.assertEqual("C", g.classify([f("src/kotoba/protocol/govern.cljk", "M", ["(x)"], [])] + B_FILES)[0])

    def test_runner_edit_must_be_registration_only(self):
        bad = [B_FILES[0], B_FILES[1], f("test/run_portable.cljk", "M", ["(System/exit 0)"], [])]
        self.assertEqual("C", g.classify(bad)[0])

    def test_runner_run_tests_line_is_registration(self):
        ok = [B_FILES[0], B_FILES[1],
              f("test/run_portable.cljk", "M", ["(t/run-tests 'kotoba.protocol.accountability-test"],
                ["(t/run-tests 'kotoba.protocol.protocol-test)"])]
        self.assertEqual("B", g.classify(ok)[0])

    def test_src_without_test_is_c(self):
        self.assertEqual("C", g.classify([B_FILES[0]])[0])

    def test_touching_the_profile_is_c(self):
        r = g.classify([f("hermes/profiles/accountability-steward/SOUL.md", "M", ["x"])])
        self.assertEqual("C", r[0])

    def test_rust_is_c(self):
        self.assertEqual("C", g.classify([f("crates/x/src/a.rs", "M", ["fn a(){}"])])[0])

    def test_empty_is_c(self):
        self.assertEqual("C", g.classify([])[0])


class Decide(unittest.TestCase):
    def test_a_is_allowed_with_no_soak(self):
        d = g.decide(info([f("docs/x.md", "M", ["a"])], age_hours=0.0, tests=None))
        self.assertEqual("ALLOW", d["verdict"])

    def test_b_with_tests_and_soak_is_allowed(self):
        self.assertEqual("ALLOW", g.decide(info(B_FILES))["verdict"])

    def test_b_is_held_during_soak(self):
        d = g.decide(info(B_FILES, age_hours=3.0))
        self.assertEqual("HOLD", d["verdict"])

    def test_b_without_new_tests_is_denied(self):
        d = g.decide(info(B_FILES, tests={"ok": True, "head_n": 138, "base_n": 138, "detail": ""}))
        self.assertEqual("DENY", d["verdict"])

    def test_b_with_failing_tests_is_denied(self):
        d = g.decide(info(B_FILES, tests={"ok": False, "head_n": 140, "base_n": 138, "detail": "1 failing"}))
        self.assertEqual("DENY", d["verdict"])

    def test_b_without_readers_is_held_not_allowed(self):
        i = info(B_FILES)
        del i["read_base"], i["read_head"]
        self.assertEqual("HOLD", g.decide(i)["verdict"])

    def test_unparsed_diff_header_is_class_c(self):
        files = g.parse_diff("diff --git weird header\n+x\n")
        self.assertEqual("C", g.classify(files)[0])

    def test_b_without_a_test_run_is_held(self):
        self.assertEqual("HOLD", g.decide(info(B_FILES, tests=None))["verdict"])

    def test_crypto_tripwire_denies(self):
        files = [f("src/kotoba/protocol/n.cljk", "A", ["(js/crypto.subtle.digest)"])] + B_FILES[1:]
        self.assertEqual("DENY", g.decide(info(files))["verdict"])

    def test_foreign_branch_is_denied(self):
        self.assertEqual("DENY", g.decide(info(B_FILES, branch="feature/x"))["verdict"])

    def test_class_b_is_not_allowed_outside_protocol(self):
        self.assertEqual("DENY", g.decide(info(B_FILES, target="server"))["verdict"])

    def test_human_hold_label_holds(self):
        self.assertEqual("HOLD", g.decide(info(B_FILES, labels=["hold"]))["verdict"])

    def test_changes_requested_holds(self):
        self.assertEqual("HOLD", g.decide(info(B_FILES, changes_requested=True))["verdict"])

    def test_pause_holds_everything(self):
        self.assertEqual("HOLD", g.decide(info([f("docs/x.md", "M", ["a"])], paused=True, tests=None))["verdict"])

    def test_daily_budget_holds(self):
        self.assertEqual("HOLD", g.decide(info(B_FILES, merged_24h=1))["verdict"])

    def test_large_diff_is_denied(self):
        files = [f("docs/x.md", "M", ["l"] * 401)]
        self.assertEqual("DENY", g.decide(info(files, tests=None))["verdict"])

    def test_unknown_target_is_denied(self):
        self.assertEqual("DENY", g.decide(info(B_FILES, target="nope"))["verdict"])


class Pinned(unittest.TestCase):
    ACC = "src/kotoba/protocol/accountability.cljk"
    SRC = ('(ns a)\n(def version 1)\n(def tiers\n  {:t0 {:disclosure-path? false}\n'
           '   :t3 {:disclosure-path? :public-log}}) ; note )\n(def other 2)\n')

    def read(self, text):
        return lambda p: text if p == self.ACC else None

    def test_same_text_is_unchanged(self):
        self.assertEqual([], g.pinned_changes(self.read(self.SRC), self.read(self.SRC)))

    def test_weakening_a_tier_is_detected(self):
        head = self.SRC.replace(":t0 {:disclosure-path? false}", ":t0 {:disclosure-path? :court}")
        self.assertEqual([f"{self.ACC}:tiers"], g.pinned_changes(self.read(self.SRC), self.read(head)))

    def test_whitespace_and_comments_outside_the_form_are_not_changes(self):
        head = self.SRC.replace("(def other 2)", "(def other 3)")
        self.assertEqual([], g.pinned_changes(self.read(self.SRC), self.read(head)))

    def test_removing_a_pinned_form_is_detected(self):
        head = self.SRC.replace("(def version 1)\n", "")
        self.assertEqual([f"{self.ACC}:version"], g.pinned_changes(self.read(self.SRC), self.read(head)))

    def test_decide_denies_a_pinned_change(self):
        head = self.SRC.replace("(def version 1)", "(def version 2)")
        d = g.decide(info(B_FILES, read_base=self.read(self.SRC), read_head=self.read(head)))
        self.assertEqual("DENY", d["verdict"])

    def test_the_real_l0_forms_are_found(self):
        path = "/Users/junkawasaki/github/kotoba-lang/kotoba-protocol"
        out = subprocess.run(["git", "-C", path, "show", "origin/main:" + self.ACC],
                             capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("kotoba-protocol checkout not available")
        for _, name in g.PINNED_FORMS:
            if _ == self.ACC:
                self.assertIsNotNone(g._form(out.stdout, name), name)


class ParseDiff(unittest.TestCase):
    def test_statuses_and_lines(self):
        patch = ("diff --git a/n.cljk b/n.cljk\nnew file mode 100644\n--- /dev/null\n+++ b/n.cljk\n@@\n+a\n+b\n"
                 "diff --git a/d.md b/d.md\n--- a/d.md\n+++ b/d.md\n@@\n-x\n+y\n")
        r = g.parse_diff(patch)
        self.assertEqual(["A", "M"], [x["status"] for x in r])
        self.assertEqual(["a", "b"], r[0]["added"])
        self.assertEqual(["x"], r[1]["removed"])


if __name__ == "__main__":
    unittest.main()
