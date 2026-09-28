# Git Version Tagger

A menu bar (macOS) / top bar (Ubuntu) app that moves version tags such as `3.25-#a1b2c3d`
to the head of a remote branch — the `tag.sh BRANCH MARKER` workflow as one click in a menu,
with an atomic push.

## Install

- **macOS:** open `GitVersionTagger-<version>-macos-<arch>.dmg`, drag the app to Applications.
  The build is not notarized, so macOS blocks the first launch: open System Settings →
  Privacy & Security and click **Open Anyway** next to the GitVersionTagger message. This allows
  only this app; do not remove the quarantine flag with `xattr`, which skips the check entirely.
- **Ubuntu 22.04/24.04:** `sudo apt install ./git-version-tagger_<version>_amd64.deb`, then start
  "Git Version Tagger" from the app grid. The icon needs the "Ubuntu AppIndicators" GNOME
  extension (enabled by default on Ubuntu).
- **From source:** `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && python -m git_version_tagger`

## Use

1. First launch opens **Settings**. Choose the project folder, then on **Branches** give every
   branch its one version (mkdev → 3.26, mkdev-rc → 3.25). Type them, or use **Import branch…**
   and **Version from remote…**.
2. Menu → **Tag mkdev → 3.26**. The tag moves immediately, with no confirmation: the new tag is
   pushed, the old `3.26-#…` tag is deleted, and the new name is copied to the clipboard.
3. **Copy tag** copies the tag of every branch; **Show log…** shows every git command.
4. After a release, open Settings → Branches → **Next release…**. Each checked branch moves to its
   next version (mkdev 3.26 → 3.27, mkdev-rc 3.25 → 3.26). Click Save, then tag the branches when
   they are ready.

Command line (same config as the app):

```
git-version-tagger tag mkdev --dry-run
git-version-tagger tag mkdev
git-version-tagger list
```

## GitHub login

If the remote is on GitHub over HTTPS, git needs a login that works without a password prompt.
Settings → General → **GitHub account** does this with the GitHub CLI:

1. Install `gh` (macOS: `brew install gh`; Ubuntu: see https://cli.github.com). The status check
   also works with the older `gh` that Ubuntu packages. If logging in fails with it, install the
   current `gh` from cli.github.com.
2. Click **Log in with GitHub…**. The window shows a one-time code (already on the clipboard). Click
   **Open GitHub in the browser**, enter the code and confirm. The window closes by itself.
3. The app then runs `gh auth setup-git`, which makes git ask `gh` for the token (it adds
   `credential.https://github.com.helper` to `~/.gitconfig`). If you logged in to `gh` earlier in a
   terminal, click **Use this login for git** instead.

The host comes from the project's remote (GitHub Enterprise works too). SSH remotes
(`git@github.com:…`) use your SSH key and do not need this login. The app stores no token: gh keeps
it in the system keychain.

## How it differs from tag.sh

It tags `origin/<branch>` after a fetch instead of checking the branch out (your working copy is
never touched), matches only `<marker>-#<hash>` tags, and replaces the tag with one atomic push so
a failure never leaves the remote without a tag.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No icon on Ubuntu | `sudo apt install gnome-shell-extension-appindicator && gnome-extensions enable ubuntu-appindicators@ubuntu.com`, log out/in |
| "cannot run 'git'" on macOS | Install Xcode Command Line Tools (`xcode-select --install`) or set Settings → Git executable (e.g. `/opt/homebrew/bin/git`) |
| Push/fetch fails with "terminal prompts disabled" or "Authentication failed" | Settings → General → GitHub account → **Log in with GitHub…** (HTTPS remotes). For SSH remotes make sure `ssh -T git@github.com` works in a terminal |
| GitHub account says "The GitHub CLI (gh) is not installed" but it is | The app looks on PATH and in `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`, `/snap/bin`; install gh in one of them |
| "does not support --atomic" in the log | Harmless; the app retried with a normal push |
| Settings file broken | The app started with defaults and kept the old file as `config.json.bak` next to `config.json` |
| After updating, Settings asks for the version of every branch | Older settings listed versions and branches separately; pick each branch's version once. The old file is kept as `config.json.v1` |

Files: config in `~/Library/Application Support/git-version-tagger/` (macOS) or
`~/.config/git-version-tagger/` (Ubuntu); log in `~/Library/Logs/git-version-tagger/` or
`~/.local/state/git-version-tagger/log/`.

## Release checklist (manual QA)

Run against a throwaway remote first (see "Try it" in the implementation plan, Task 9 Step 7).

macOS (light and dark menu bar):
- [ ] Icon visible in the menu bar, no Dock icon; second launch says "already running"
- [ ] First launch opens Settings; Save rejects a folder that is not a git repo
- [ ] Tag ▸ marker → no dialog; notification, clipboard holds the new tag, `git ls-remote --tags origin` shows it, old tag gone; the log lists the delete/create lines
- [ ] Same marker again → "Nothing to do"
- [ ] Wi-Fi off → Tag ▸ marker → error dialog, ⚠ line in the menu; after Wi-Fi on the remote still has the old tag
- [ ] Start at login on → log out/in → app running; off → LaunchAgent plist removed
- [ ] Log window lists the git commands
- [ ] Branches tab: edit a version in place, a duplicate version is refused, Next release… moves the checked branches
- [ ] Menu shows one "Tag <branch> → <version>" per branch and stays narrow with an error shown
- [ ] Settings → General → GitHub account: Log in with GitHub… shows a code, copies it, opens the device page; afterwards the status shows "Logged in to github.com as <you>" and tagging works over HTTPS

Ubuntu 22.04 and 24.04, both "Ubuntu" (Wayland) and "Ubuntu on Xorg" sessions:
- [ ] White icon in the top bar; menu opens on click
- [ ] Every macOS item above (start at login → `~/.config/autostart/git-version-tagger.desktop`)
- [ ] `git-version-tagger tag mkdev --dry-run` works from a terminal
- [ ] Branches tab: edit a version in place, a duplicate version is refused, Next release… moves the checked branches
- [ ] Settings → General → GitHub account: Log in with GitHub… shows a code, copies it, opens the device page; afterwards the status shows "Logged in to github.com as <you>" and tagging works over HTTPS
