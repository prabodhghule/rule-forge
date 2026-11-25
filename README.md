# Rule Forge

A web page where people describe a detection rule (the requirement plus any logic they have). Claude writes the query and publishes it on the page under **Rules**.

```
Web form ──► GitHub Issue ──► Scheduled Claude task (runs every hour)
                                    │
                                    ├─► rules/issue-<n>.json   (saved in the repo)
                                    ├─► comment on the issue   (query + explanation)
                                    └─► push ──► website redeploys (shows up under Rules)
```

You don't need a server or an Anthropic API key. A scheduled Claude task, running on your Claude plan, does the work every hour. It follows `prompts/scheduled-task.md`, and the helper scripts are `scripts/pending.py` and `scripts/save_rule.py`.

## Setup (already done for prabodhghule/rule-forge)

1. The repo exists, and the Claude GitHub App has access to it.
2. The labels `rule-request` and `rule-generated` exist.
3. Pages is set to deploy from **GitHub Actions**.
4. A scheduled Claude task checks for new requests every hour.

### Optional: instant mode with an API key
If you get an Anthropic API key later, add it as the `ANTHROPIC_API_KEY` secret and uncomment the triggers in `.github/workflows/generate-rule.yml`. Rules are then written within 1–2 minutes of each request.

## Using it

- **Request a rule.** Fill in the form on the site and click **Copy request & open GitHub**. In the GitHub tab, sign in if asked, paste (Ctrl+V) into the Request box, and press *Create*. A free GitHub account is required.
- **Get the result.** Within about an hour, Claude comments on the issue with the query, and the rule appears under Rules. Until then it is listed as "In progress".
- **Revise it.** Comment `/regenerate make it 7-day lookback and exclude service accounts` on the issue. Claude rewrites the rule using the previous query plus your feedback, and the revision number goes up.
- **Requests from outsiders.** If someone outside your collaborators opens an issue, a maintainer can comment `/regenerate` to run it.

## Ask Claude (general prompts)

The site also has an **Ask Claude** page (`docs/ask.html`) for any question, not just rules.

- **Ask.** Write a prompt, click **Copy prompt & open GitHub**, paste it into the issue form and press *Create*. The issue is titled `[Ask] …` and labelled `ask-claude`.
- **Get the answer.** The same hourly scheduled task answers it (see `prompts/ask-task.md`), comments the answer on the issue, adds the `answered` label, and publishes it on the Ask Claude page.
- **Follow up.** Comment `/followup <your next question>` on the issue. Claude answers with the earlier conversation as context.
- At most 10 prompts are answered per run (`MAX_ASKS_PER_RUN`). Answers are public and pass the same sensitive-data checks as rules.

## Make Claude better at your environment

- `prompts/system.md`: Claude's instructions (style, language rules, safety).
- `knowledge/`: add `.md` files with your real dataset names, fields, naming conventions and standard exclusions. They are included in every request.

## Files

```
.github/ISSUE_TEMPLATE/rule-request.yml   the request form on GitHub
.github/workflows/generate-rule.yml       optional API-key mode (off by default)
.github/workflows/deploy-pages.yml        publishes docs/ to GitHub Pages
scripts/pending.py                        lists requests that need a rule
scripts/save_rule.py                      saves a rule, comments, labels
prompts/scheduled-task.md                 what the scheduled Claude task does
scripts/generate_rule.py                  API-key mode: issue → Claude API → rule
scripts/build_index.py                    rules/*.json → docs/data/rules.json, answers/*.json → docs/data/answers.json
scripts/pending_asks.py                   lists Ask Claude prompts that need an answer
scripts/save_answer.py                    saves an answer, comments, labels
prompts/ask-task.md                       how the scheduled task answers Ask Claude prompts
.github/ISSUE_TEMPLATE/ask-claude.yml     the Ask Claude issue form
docs/                                     the website (index.html + app.js for rules, ask.html + ask.js for Ask Claude)
```

## Security notes

- Issue text is untrusted. Claude is told to treat it only as a description of a rule. Requests from anyone are processed (ALLOWED_ASSOCIATIONS defaults to ALL in scripts/pending.py; set it to OWNER,MEMBER,COLLABORATOR to restrict).
- The site renders all rule content as text, never as HTML, so a crafted request can't inject script.
- Generated queries are drafts. Review and test them before you deploy them to production.
