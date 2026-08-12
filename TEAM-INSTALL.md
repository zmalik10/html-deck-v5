# Install the SmartBuild Deck Skill (for teammates)

You don't need to know git or Python. Claude does the whole install for you.

**Before you start (one time):** ask Zain to invite your GitHub account to the
`zmalik10/html-deck-v5` repository, and accept the email invite.

Then open Claude Code on your Mac, paste this whole block in, and press enter:

```
Install the SmartBuild html-deck-v5 deck skill on this machine and get it fully working:

1. Check GitHub access: run `gh auth status`. If gh is missing or I'm not logged in,
   walk me through logging in to GitHub first (my account has access to
   github.com/zmalik10/html-deck-v5).
2. Clone the skill into place:
   git clone https://github.com/zmalik10/html-deck-v5.git ~/.claude/skills/html-deck-v5
   If that folder already exists, run `git pull --ff-only` in it instead.
3. Install the dependencies:
   pip3 install -r ~/.claude/skills/html-deck-v5/requirements.txt
   python3 -m playwright install chromium
4. Verify the install by running:
   python3 ~/.claude/skills/html-deck-v5/packaging/preflight.py
   and fix anything it flags until it passes.
5. Add a SessionStart hook to my ~/.claude/settings.json (merge, don't overwrite) that
   quietly runs: cd ~/.claude/skills/html-deck-v5 && git pull --ff-only
   so I always start with the team's latest version of the skill.
6. When everything passes, tell me it's ready and that I can build a deck by simply
   asking for one (e.g. "build me a SmartBuild pitch deck about X") - the skill loads
   automatically. Remind me to restart Claude Code once so it picks up the new skill.
```

That's it. After the one-time install, updates are automatic: every time Claude Code
starts, the hook pulls the latest version of the skill from GitHub.

## How improvements flow (read once)

- The GitHub repo is the single source of truth.
- Fixes and upgrades are made on one machine, pushed to GitHub, and everyone's
  SessionStart hook pulls them automatically.
- If a deck looks wrong on your machine, don't edit the skill files yourself - tell
  Zain (or open an issue on the repo) so the fix lands for everyone.
