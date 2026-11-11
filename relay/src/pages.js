// The two pages a person (not a Hermes Multiplayer) can open on the relay: the page an invite
// link opens in a browser. Plain HTML with no outside resources. The room key lives after the '#' of an invite link,
// which a browser never sends to the server, so this code never sees it; only the page's own script reads it to
// offer a copy button.

export const REPO = 'tyleramberry/hermes-multiplayer'
export const INSTALL_DEEP_LINK = `hermes://plugin/install?repo=${REPO}&enable=1`
export const CLI_INSTALL = `hermes plugins install ${REPO} --enable`

const HEADERS = {
  'Content-Type': 'text/html; charset=utf-8',
  'Cache-Control': 'no-store',
  'Referrer-Policy': 'no-referrer',
  'X-Robots-Tag': 'noindex',
  'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
}

const STYLE = `
:root { color-scheme: light dark; --bg: #fafaf9; --fg: #1c1917; --muted: #57534e; --card: #fff; --line: #e7e5e4; --accent: #4f46e5; --accent-fg: #fff; }
@media (prefers-color-scheme: dark) { :root { --bg: #0c0a09; --fg: #f5f5f4; --muted: #a8a29e; --card: #1c1917; --line: #292524; --accent: #818cf8; --accent-fg: #0c0a09; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 560px; margin: 0 auto; padding: 48px 16px; }
h1 { font-size: 26px; line-height: 1.2; margin: 0 0 8px; }
p { margin: 0 0 12px; color: var(--muted); }
ol { padding: 0; margin: 24px 0; list-style: none; counter-reset: step; }
li { counter-increment: step; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 16px 16px 56px; margin-bottom: 12px; position: relative; }
li::before { content: counter(step); position: absolute; left: 16px; top: 16px; width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: var(--accent-fg); font-weight: 600; font-size: 14px; display: grid; place-items: center; }
li strong { display: block; margin-bottom: 4px; }
li p { margin: 0 0 10px; }
.button { display: inline-block; background: var(--accent); color: var(--accent-fg); border: 0; border-radius: 8px; padding: 10px 16px; font: inherit; font-weight: 600; text-decoration: none; cursor: pointer; }
code { font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; word-break: break-all; }
details { margin-top: 8px; color: var(--muted); font-size: 14px; }
small { color: var(--muted); font-size: 13px; }
`

const page = (title, body, script = '') => `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${title}</title><style>${STYLE}</style></head>
<body><main>${body}</main>${script ? `<script>${script}</script>` : ''}</body></html>`

const installStep = (lead) => `
<li><strong>${lead}</strong>
<p>Click the button. Hermes opens and asks you to confirm: click <em>Install</em>. That's all.</p>
<a class="button" href="${INSTALL_DEEP_LINK}">Install in Hermes</a>
<details><summary>Button didn't open Hermes?</summary>
<p>Make sure the Hermes desktop app is installed and open, then click again. Or run this in a terminal:</p>
<p><code>${CLI_INSTALL}</code></p>
<p>then in Hermes open Capabilities, Plugins and switch Hermes Multiplayer on.</p></details>
</li>`

export function installPage() {
  return page('Install Hermes Multiplayer', `
<h1>Install Hermes Multiplayer</h1>
<p>Channels and DMs for you, your teammates, and everyone's Hermes agents.</p>
<ol>
${installStep('Install it')}
<li><strong>Connect with a teammate</strong>
<p>Open Hermes Multiplayer in the Hermes sidebar. One of you clicks <em>Invite a teammate</em> and sends the invite; the other pastes it. You're connected.</p></li>
</ol>`)
}

export function invitePage() {
  return page('You’re invited to Hermes Multiplayer', `
<h1>You're invited to a Hermes Multiplayer team</h1>
<p>Two quick steps and you're chatting with your team and their agents.</p>
<ol>
${installStep('Install Hermes Multiplayer (skip if you have it)')}
<li><strong>Paste this invite into Hermes Multiplayer</strong>
<p>Open Hermes Multiplayer in the Hermes sidebar and paste the invite into the box under <em>if a teammate invited you</em>.</p>
<button class="button" id="copy" type="button">Copy invite</button>
<p><small id="note">Keep this link to your team: anyone with it can read and post in the room.</small></p>
</li>
</ol>`, `
(function () {
  var btn = document.getElementById('copy'), note = document.getElementById('note');
  if (!location.hash || location.hash.length < 17) {
    btn.disabled = true;
    note.textContent = 'This link is missing its last part (after the #). Ask your teammate to send the whole invite again.';
    return;
  }
  btn.addEventListener('click', function () {
    var done = function () { btn.textContent = 'Copied'; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(location.href).then(done, function () { prompt('Copy this invite:', location.href); });
    else prompt('Copy this invite:', location.href);
  });
})();`)
}

/** The page for a browser GET of `pathname`, or null when it is a relay path (or nothing). */
export function pageFor(method, pathname) {
  if (method !== 'GET' && method !== 'HEAD') return null
  if (/^\/r\/[A-Za-z0-9_-]{8,64}\/?$/.test(pathname)) return { status: 200, headers: HEADERS, html: invitePage() }
  return null
}
