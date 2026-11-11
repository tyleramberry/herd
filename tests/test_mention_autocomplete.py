"""S-9: the @-mention token the desktop composer inserts must trigger the S-7 wake.

The handle is computed in JS (`mentionHandle` in desktop/plugin.js); this test runs that exact
function under node (skipped if node is missing) and feeds the result to the Python parser.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pkg  # noqa: E402

_pkg_mod, store, _tools = _pkg.load()
JS = (_pkg.ROOT / "desktop/plugin.js").read_text()
# İlker (dotted capital I), Kate with the Kelvin sign U+212A and Émile (accented
# capital) are the QA-found cases: the old slug-then-keep-case handle produced
# "@lker" / "@ate" / no handle at all, which the backend never matched.
NAMES = [
    "Tyler", "tyler", "Tyler Amberry", "  Brooklyn  ", "Mary-Jane O'Neil",
    "Dr. Who?", "A", "R2 D2",
    "İlker", "Kate\u212a", "Émile",
]


def js_eval(expr_template: str, names):
    fn = re.search(r"function mentionHandle\(name\) \{.*?\n\}\n", JS, re.S).group(0)
    script = fn + f"\nconst names = {json.dumps(names)};\nconsole.log(JSON.stringify(names.map(n => {expr_template})))"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def js_regex(varname: str):
    """The JS `const <varname> = /…/flags` literal, as (source, flags)."""
    match = re.search(rf"const {varname} = /(.+)/([a-z]*)\n", JS)
    return match.group(1), match.group(2)


def js_find(varname: str, texts):
    src, flags = js_regex(varname)
    script = (
        f"const rx = new RegExp({json.dumps(src)}, {json.dumps(flags)});"
        f"const texts = {json.dumps(texts)};"
        "console.log(JSON.stringify(texts.map(t => { const m = t.match(rx); return m ? m[0] : null })));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class MentionRoundTrip(unittest.TestCase):
    def test_inserted_human_and_agent_tokens_wake_the_participant(self):
        handles = js_eval("mentionHandle(n)", NAMES)
        for name, handle in zip(NAMES, handles):
            self.assertTrue(handle, name)
            for token in ("@" + handle, "@" + handle + "-hermes"):
                # the composer inserts "<token> " mid-sentence
                self.assertTrue(store.mentions_me(f"hey {token} please look", name), (name, token))
                self.assertTrue(store.mentions_me(f"{token} ", name), (name, token))

    def test_token_matches_the_highlight_regex(self):
        handles = js_eval("mentionHandle(n)", NAMES)
        rx = re.compile(r"(?<![\w@])@[A-Za-z0-9][A-Za-z0-9_-]*")
        for handle in handles:
            self.assertEqual(rx.fullmatch("@" + handle).group(0), "@" + handle)

    def test_js_regexes_match_backend(self):
        # The boundary class must be Unicode-aware, like Python's \w; an ASCII \w
        # made "é@ty" look like a mention in JS while the backend never woke.
        self.assertIn(r"(?<![\p{L}\p{N}_@])@[A-Za-z0-9][A-Za-z0-9_-]*", JS)
        self.assertNotIn(r"(?<![\w@])@[A-Za-z0-9]", JS)

    def test_unicode_boundary_matches_backend(self):
        # Parity with multiplayer_store.mentions_me's lookbehind for the QA-found cases.
        # Boundary detection only — whether the handle names a *specific* person is
        # mentions_me's job, and "@ty" is a mention of someone who isn't Tyler.
        texts = ["hi @ty", "@ty", "x@ty", "(ty@ty", "é@ty", "\u212a@ty", "İ@ty"]
        tokens = js_find("MENTION_TOKEN", texts)
        for text, token in zip(texts, tokens):
            expected = bool(re.search(r"(?<![\w@])@[A-Za-z0-9][A-Za-z0-9_-]*", text))
            self.assertEqual(bool(token), expected, text)

    def test_trigger_body_accepts_any_script(self):
        # Typing an accented name after @ must keep the menu open (S3 finding).
        for text in ["@İl", "@Ém", "@K\u212a", "@ty"]:
            self.assertIsNotNone(js_find("MENTION_TRIGGER", [text])[0], text)

    def test_dropdown_wiring_present(self):
        for needle in ("MentionMenu", "mentionCandidates", "renderContent", "ArrowDown", "'Tab'", "'Escape'"):
            self.assertIn(needle, JS)

    def test_insert_mention_consumes_the_word_tail(self):
        """Picking with the caret mid-word must not leave the tail behind (QA F3)."""
        fn = re.search(r"function insertMention\(textarea, state, handle, \$mention\) \{.*?\n\}\n", JS, re.S).group(0)
        script = fn + """
const cases = [
  { value: 'hey @peerXYZ', caret: 9 },
  { value: 'hey @peerXYZ', caret: 12 },
  { value: 'start @peerXYZ end', caret: 11 },
];
console.log(JSON.stringify(cases.map(c => {
  const ta = { value: c.value, selectionStart: c.caret, focus() {}, setSelectionRange(a) { this.caret = a } };
  insertMention(ta, { start: c.value.indexOf('@') }, 'Peer-One', { set() {} });
  return [ta.value, ta.caret];
})));
"""
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out[0], ["hey @Peer-One ", 14])          # caret inside the word run
        self.assertEqual(out[1], ["hey @Peer-One ", 14])          # caret at the end of it
        self.assertEqual(out[2], ["start @Peer-One  end", 16])    # surrounding text kept

    def test_shift_enter_does_not_pick_a_mention(self):
        """Shift+Enter means newline even with the menu open (QA F4)."""
        self.assertIn("(e.key === 'Enter' && !e.shiftKey) || e.key === 'Tab'", JS)
        self.assertNotIn("if (e.key === 'Enter' || e.key === 'Tab')", JS)
        # the submit path guards Shift+Enter too, so the key falls through to a newline
        self.assertIn("if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing)", JS)


if __name__ == "__main__":
    unittest.main()
