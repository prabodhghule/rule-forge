# Rule Forge

A web page where people describe a detection rule (the requirement plus any logic they have). Claude writes the query and publishes it on the page under **Rules**.

```
Web form ──► GitHub Issue ──► GitHub Action ──► Claude API
                                    │
                                    ├─► rules/issue-<n>.json   (saved in the repo)
                                    ├─► comment on the issue   (query + explanation)
                                    └─► redeploys the website  (shows up under Rules)
```

You don't need to run a server. The site is static (GitHub Pages), and your Anthropic API key stays in GitHub Secrets.

## Setup (about 5 minutes)

1. **Create the repo.** Push this folder to a new GitHub repository with `main` as the default branch.
2. **Add your API key.** Go to *Settings → Secrets and variables → Actions → New repository secret*, name it `ANTHROPIC_API_KEY` and paste the key from console.anthropic.com.
3. **Turn on Pages.** Go to *Settings → Pages → Build and deployment → Source*, choose **GitHub Actions**, then open *Actions → Deploy website → Run workflow* once.
4. **Create the label.** Go to *Issues → Labels → New label* and name it `rule-request`. The issue form applies it automatically.
5. Open `https://<you>.github.io/<repo>/` and submit a test rule.

### Optional settings (*Settings → Secrets and variables → Actions → Variables*)

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Model to use, e.g. `claude-opus-5-5` for harder rules |
| `ALLOWED_ASSOCIATIONS` | `OWNER,MEMBER,COLLABORATOR` | Who triggers generation automatically. Set `ALL` to allow anyone (watch your API costs on a public repo) |
| `SITE_URL` | `https://<owner>.github.io/<repo>/` | Set this if you use a custom domain |

If you use a custom domain, also set `owner` and `repo` in `docs/config.js`.

## Using it

- **Request a rule.** Fill in the form on the site. It opens a pre-filled GitHub issue; press *Create*.
- **Get the result.** About 1–2 minutes later Claude comments on the issue with the query, and the rule appears under Rules. Until then it is listed as "In progress".
- **Revise it.** Comment `/regenerate make it 7-day lookback and exclude service accounts` on the issue. Claude rewrites the rule using the previous query plus your feedback, and the revision number goes up.
- **Requests from outsiders.** If someone outside your collaborators opens an issue, a maintainer can comment `/regenerate` to run it.

## Make Claude better at your environment

- `prompts/system.md`: Claude's instructions (style, language rules, safety).
- `knowledge/`: add `.md` files with your real dataset names, fields, naming conventions and standard exclusions. They are included in every request.

## Files

```
.github/ISSUE_TEMPLATE/rule-request.yml   the request form on GitHub
.github/workflows/generate-rule.yml       calls Claude, commits the rule, comments, deploys
.github/workflows/deploy-pages.yml        publishes docs/ to GitHub Pages
scripts/generate_rule.py                  issue → Claude → rules/issue-<n>.json
scripts/build_index.py                    rules/*.json → docs/data/rules.json
docs/                                     the website (index.html, app.js, style.css, config.js)
```

## Security notes

- Issue text is untrusted. The workflow passes it through environment variables, never into shell commands, and the system prompt tells Claude to ignore instructions inside requests.
- The site renders all rule content as text, never as HTML, so a crafted request can't inject script.
- Generated queries are drafts. Review and test them before you deploy them to production.
