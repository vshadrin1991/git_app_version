# Git Version Tagger

A menu bar (macOS) / top bar (Ubuntu) app that moves version tags such as `3.25-#a1b2c3d`
to the head of a remote branch — the `tag.sh BRANCH MARKER` workflow as one click in a menu,
with an atomic push.

## Install

### Get the package

The installers are built by GitHub Actions on every push to `main`:

1. Open the repository's **Actions** tab → **build** workflow → the latest green run.
2. Under **Artifacts**, download `git-version-tagger-macos-14` (macOS) or
   `git-version-tagger-ubuntu-22.04` (Ubuntu). You must be logged in to GitHub to download.
3. Unzip it. Inside is `GitVersionTagger-<version>-macos-arm64.dmg` or
   `git-version-tagger_<version>_amd64.deb`.

Or build it yourself, see [Build from source](#build-from-source).

### macOS (Apple silicon)

1. Open the `.dmg` and drag **GitVersionTagger** to **Applications**.
2. Start it from Applications. The app is not notarized, so macOS refuses the first launch.
   Open **System Settings → Privacy & Security**, scroll down and click **Open Anyway** next to the
   GitVersionTagger message, then confirm. This is needed once. Do not remove the quarantine flag
   with `xattr`: that skips the check for the whole app instead of approving it.
3. The icon appears in the menu bar (there is no Dock icon). Settings opens on the first launch.
4. git must be installed: run `xcode-select --install` if `git --version` in Terminal asks for it.

To update, quit the app from its menu and replace it in Applications. Settings are kept.
To uninstall, quit it, delete it from Applications and, if you want, remove
`~/Library/Application Support/git-version-tagger/`.

### Ubuntu 22.04 / 24.04 (amd64)

1. Install the package (apt pulls in `git` and the AppIndicator extension):

   ```bash
   sudo apt install ./git-version-tagger_<version>_amd64.deb
   ```

2. Start **Git Version Tagger** from the app grid, or run `git-version-tagger` in a terminal.
3. If no icon appears in the top bar, enable the extension and log out and back in:

   ```bash
   gnome-extensions enable ubuntu-appindicators@ubuntu.com
   ```

To update, install the new `.deb` the same way. To uninstall: `sudo apt remove git-version-tagger`.

The `git-version-tagger` command (see [Use](#use)) is installed into `/usr/bin` with the package.
On macOS the app binary takes the same arguments; add an alias to `~/.zshrc` to use it:

```bash
alias git-version-tagger=/Applications/GitVersionTagger.app/Contents/MacOS/GitVersionTagger
```

### Build from source

Needs Python 3.10+ and git.

```bash
git clone https://github.com/vshadrin1991/git_app_version.git
cd git_app_version
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m git_version_tagger      # run the app
pytest                            # run the tests
```

To build the installers:

- macOS: `packaging/macos/build.sh` → `dist/GitVersionTagger-<version>-macos-<arch>.dmg`
- Ubuntu: `packaging/linux/build-deb.sh` on Ubuntu, or `packaging/linux/build-in-docker.sh` from
  any machine with Docker → `dist/git-version-tagger_<version>_amd64.deb`

## Use

1. First launch opens **Settings**. Choose the project folder, then on **Branches** add one row per
   branch and version (trunk → 3.25, trunk → alt-1.55, trunk-rc → 3.24). A branch can have several
   versions; the same branch and version can be listed only once, and a version belongs to one branch.
   Type them, or use **Import branch…** and **Version from remote…**.
2. Menu → **Tag trunk → 3.26**. The tag moves immediately, with no confirmation: the new tag is
   pushed, the old `3.26-#…` tag is deleted, and the new name is copied to the clipboard.
3. **Copy tag** copies the tag of every branch; **Show log…** shows every git command.
4. After a release, open Settings → Branches → **Next release…**. Each checked row moves to its
   next version (trunk 3.26 → 3.27, trunk-rc 3.25 → 3.26). Click Save, then tag the branches when
   they are ready.

Command line (same config as the app):

```
git-version-tagger tag trunk --dry-run
git-version-tagger tag trunk
git-version-tagger tag trunk alt-1.55
git-version-tagger list
```

`tag BRANCH` without a version works when the branch has one version in Settings; when it has
several, name the one to move (`tag trunk alt-1.55`).

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
| An older version of the app says "Duplicate branch 'trunk'" | That version allows one row per branch. Update the app, or remove the extra trunk rows |

Files: config in `~/Library/Application Support/git-version-tagger/` (macOS) or
`~/.config/git-version-tagger/` (Ubuntu); log in `~/Library/Logs/git-version-tagger/` or
`~/.local/state/git-version-tagger/log/`.
