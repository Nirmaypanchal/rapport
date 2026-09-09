# Create the Reddit bot account and add its API credentials as repository secrets

**Why:** the Community agent listens to r/rapport already (public reads need no login) but can only answer people and post
updates through the `reddit-post` workflow, which needs credentials. Until then its replies pile up in `sprint/reddit/failed/`.

**What to do:**
1. Create (or pick) the Reddit account the bot will post as. A dedicated account such as `u/rapport-sprint` is clearest;
   turn two-factor authentication off on it (the script grant does not support 2FA). Make it a moderator of r/rapport so its
   posts skip the new-account spam filter, and give it a user flair like "sprint bot".
2. Logged in as that account, open https://www.reddit.com/prefs/apps and click "create another app…": name `rapport-sprint`,
   type **script**, redirect URI `http://localhost:8080`. Note the client id (the short string under the app name) and the secret.
3. In a terminal, from the repository folder, run:
   ```
   gh secret set REDDIT_CLIENT_ID
   gh secret set REDDIT_CLIENT_SECRET
   gh secret set REDDIT_USERNAME
   gh secret set REDDIT_PASSWORD
   ```
   (each command prompts for the value).
4. Optional test: `gh workflow run "Reddit post"`; the run should print "outbox empty".
5. Close this issue. The sprint moves this file to `done/`.

**Blocked:** every reply and update on r/rapport; release announcements on r/rapport.
