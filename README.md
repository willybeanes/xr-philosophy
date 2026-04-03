# xR Philosophy

A Bluesky bot and minimal website that posts MLB game scores annotated with **xR** (expected runs), calculated using RE24 — run expectancy based on the 24 base-out states.

Inspired by @xGPhilosophy on X/Twitter, but for baseball.

## What is xR?

**Expected Runs (xR)** measures how many runs a team *should* have scored based on the base-out situations they created throughout a game.

Every plate appearance starts with a base-out state (e.g., runner on first, one out) that has a known expected run value. After the play, the new state has a different expected value. The difference — plus any runs that actually scored — is the **ΔRE** for that plate appearance.

Summing ΔRE across all plate appearances for a team gives their **xR** for the game. When a team's actual runs differ significantly from their xR, it suggests they were lucky (or unlucky) with sequencing.

The bot uses the standard 2010–2019 MLB average RE24 matrix.

## Example post

```
New York Yankees (3.8 xR) 5 – 2 (1.9 xR) Boston Red Sox 🔴
#MLB #xR #Yankees #RedSox
```

The 🔴 means the team with higher xR actually lost.

## Setup

1. **Fork this repo**
2. **Enable GitHub Pages** — go to Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/docs`
3. **Add repository secrets** — go to Settings → Secrets and variables → Actions → New repository secret:
   - `BLUESKY_HANDLE` — your Bluesky handle (e.g., `xrphilosophy.bsky.social`)
   - `BLUESKY_APP_PASSWORD` — generate one at [Bluesky Settings → App passwords](https://bsky.app/settings/app-passwords)
4. **Enable GitHub Actions** — the workflow runs every 15 minutes during game hours (6 PM – 1 AM ET, April–October)
5. **Test manually** — go to Actions → "xR Bot" → "Run workflow" to trigger a test run

### Dry run mode

Set the `DRY_RUN=true` environment variable to compute and log xR values without posting to Bluesky. Useful for testing.

### Test a single game

```bash
pip install -r requirements.txt
python test_single_game.py <gamePk>
```

Find gamePk values at `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD`.

## How it works

1. GitHub Actions triggers the bot on a schedule during baseball season
2. The bot fetches today's final regular-season games from the MLB Stats API
3. For each new game, it fetches play-by-play data and calculates xR via RE24
4. Results are posted to Bluesky and saved to `data/scores.json`
5. The dashboard at `docs/index.html` is regenerated
6. State files are committed back to the repo

## Tech stack

- **Python 3.11** — no external frameworks
- **MLB Stats API** — free, no auth required
- **AT Protocol** (atproto) — Bluesky posting
- **GitHub Actions** — scheduling and CI/CD
- **GitHub Pages** — static dashboard hosting
