IG Finder v3 — GitHub Actions edition

WHY
- You can close Safari/iPhone. GitHub Actions runs in GitHub's runner, not your Codespace.
- Scheduled every 15 minutes at minutes 02/17/32/47.
- You can also run it manually from Actions > IG Username Finder > Run workflow.

SETUP
1. Keep the repo PRIVATE.
2. Repository > Settings > Secrets and variables > Actions > New repository secret.
3. Name: DISCORD_WEBHOOK
4. Value: your Discord webhook URL.
5. Upload ALL files/folders from this ZIP to the repository root and commit.
6. Open Actions and enable workflows if GitHub asks.

IMPORTANT
This checker only uses public web responses. A candidate is NOT a 100% guarantee that Instagram will permit claiming it.
