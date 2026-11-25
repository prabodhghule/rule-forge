(() => {
  "use strict";
  const cfg = Object.assign({ owner: "", repo: "", siteTitle: "Rule Forge" }, window.RULE_FORGE || {});
  if (!cfg.owner && location.hostname.endsWith(".github.io")) {
    cfg.owner = location.hostname.split(".")[0];
    cfg.repo = cfg.repo || location.pathname.split("/").filter(Boolean)[0] || location.hostname;
  }
  const repoUrl = cfg.owner && cfg.repo ? `https://github.com/${cfg.owner}/${cfg.repo}` : "";
  const $ = (s, el = document) => el.querySelector(s);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  $("#site-title").textContent = cfg.siteTitle;
  if (repoUrl) $("#repo-link").href = repoUrl; else $("#repo-link").hidden = true;

  // Safe Markdown: escape everything first, then add a few tags. Links only for https://.
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inl = (t) => t
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener nofollow">$1</a>');
  function md(src) {
    const blocks = [];
    const s = esc(src).replace(/```[^\n]*\n([\s\S]*?)```/g, (_, code) => { blocks.push(code); return `\u0000${blocks.length - 1}\u0000`; });
    const out = [];
    for (const para of s.split(/\n{2,}/)) {
      const t = para.trim(); if (!t) continue;
      const lines = t.split("\n");
      if (/^\u0000\d+\u0000$/.test(t)) { out.push(t); continue; }
      if (lines.every((l) => /^\s*[-*] /.test(l))) { out.push("<ul>" + lines.map((l) => `<li>${inl(l.replace(/^\s*[-*] /, ""))}</li>`).join("") + "</ul>"); continue; }
      if (lines.every((l) => /^\s*\d+[.)] /.test(l))) { out.push("<ol>" + lines.map((l) => `<li>${inl(l.replace(/^\s*\d+[.)] /, ""))}</li>`).join("") + "</ol>"); continue; }
      const h = t.match(/^#{1,4} (.*)$/);
      if (h && lines.length === 1) { out.push(`<h4>${inl(h[1])}</h4>`); continue; }
      out.push(`<p>${lines.map(inl).join("<br>")}</p>`);
    }
    return out.join("").replace(/\u0000(\d+)\u0000/g, (_, i) => `<pre><code>${blocks[i]}</code></pre>`);
  }

  // ---------- Form: copy prompt + open GitHub ----------
  function copyText(text) {
    const ta = el("textarea"); ta.value = text; ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove(); return ok;
  }
  let last = "";
  $("#ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const err = $("#form-error"); err.hidden = true;
    const prompt = $("#prompt").value.trim();
    if (!repoUrl) { err.textContent = "Repository not configured. Set owner and repo in docs/config.js."; err.hidden = false; return; }
    if (!prompt) { err.textContent = "Write a prompt first."; err.hidden = false; return; }
    last = prompt;
    const ok = copyText(last);
    const title = "[Ask] " + prompt.replace(/\s+/g, " ").slice(0, 90) + (prompt.length > 90 ? "…" : "");
    const params = new URLSearchParams({ template: "ask-claude.yml", title });
    window.open(`${repoUrl}/issues/new?${params}`, "_blank", "noopener");
    $("#copy-status").textContent = ok ? "Your prompt is copied." : "Copy the text below first (select it and press Ctrl+C).";
    $("#ask-text").value = last;
    $("#submit-help").hidden = false;
    $("#submit-help").scrollIntoView({ block: "nearest" });
  });
  $("#copy-again").addEventListener("click", () => {
    const ok = copyText(last);
    $("#copy-again").textContent = ok ? "Copied" : "Select the text and press Ctrl+C";
    setTimeout(() => { $("#copy-again").textContent = "Copy again"; }, 1500);
  });

  // ---------- Answers ----------
  let items = [];
  const when = (t) => { try { return new Date(t).toLocaleString(); } catch { return ""; } };

  function renderItem(rec) {
    const art = el("article", null, "rule"); art.id = `ask-${rec.issue}`;
    const head = el("button", null, "rule-head"); head.type = "button"; head.setAttribute("aria-expanded", "false");
    head.append(el("span", "Q", "sev ask-badge"), el("span", rec.title, "rule-title"),
      el("span", `${(rec.turns || []).length} answer${(rec.turns || []).length === 1 ? "" : "s"}`, "lang"), el("span", "▾", "chev"));
    const body = el("div", null, "rule-body"); body.hidden = true;
    (rec.turns || []).forEach((t, i) => {
      const turn = el("div", null, "turn");
      turn.appendChild(el("h4", i === 0 ? "Prompt" : "Follow-up"));
      turn.appendChild(el("p", t.prompt, "ask-q"));
      turn.appendChild(el("h4", "Claude"));
      const a = el("div", null, "answer"); a.innerHTML = md(t.answer); turn.appendChild(a);
      const copy = el("button", "Copy answer", "secondary"); copy.type = "button";
      copy.addEventListener("click", async () => { try { await navigator.clipboard.writeText(t.answer); copy.textContent = "Copied"; } catch { copy.textContent = "Copy blocked"; } });
      turn.appendChild(copy);
      body.appendChild(turn);
    });
    const meta = el("div", null, "meta");
    if (rec.issue_url) { const l = el("a", `Issue #${rec.issue} · continue with /followup`); l.href = rec.issue_url; l.target = "_blank"; l.rel = "noopener"; meta.appendChild(l); }
    if (rec.asked_by) meta.appendChild(el("span", `by @${rec.asked_by}`));
    meta.appendChild(el("span", when(rec.updated_at)));
    body.appendChild(meta);
    head.addEventListener("click", () => { const open = head.getAttribute("aria-expanded") !== "true"; head.setAttribute("aria-expanded", String(open)); body.hidden = !open; });
    art.append(head, body);
    return art;
  }

  function render() {
    const q = $("#search").value.trim().toLowerCase();
    const shown = items.filter((r) => !q || [r.title, ...(r.turns || []).flatMap((t) => [t.prompt, t.answer])].join(" ").toLowerCase().includes(q));
    $("#list").replaceChildren(...shown.map(renderItem));
    $("#count").textContent = items.length ? `(${shown.length}${shown.length !== items.length ? ` of ${items.length}` : ""})` : "";
    $("#empty").hidden = items.length > 0;
    const m = location.hash.match(/^#ask-(\d+)$/);
    const node = m && document.getElementById(`ask-${m[1]}`);
    if (node) { $(".rule-head", node).setAttribute("aria-expanded", "true"); $(".rule-body", node).hidden = false; node.scrollIntoView({ block: "start" }); }
  }
  $("#search").addEventListener("input", render);
  window.addEventListener("hashchange", render);

  fetch(`data/answers.json?t=${Date.now()}`).then((r) => (r.ok ? r.json() : [])).catch(() => [])
    .then((data) => { items = Array.isArray(data) ? data : []; render(); loadPending(); });

  function loadPending() {
    if (!repoUrl) return;
    fetch(`https://api.github.com/repos/${cfg.owner}/${cfg.repo}/issues?state=open&per_page=50`)
      .then((r) => (r.ok ? r.json() : [])).then((issues) => {
        const done = new Set(items.map((r) => r.issue));
        const waiting = issues.filter((i) => !i.pull_request && !done.has(i.number) &&
          ((i.labels || []).some((l) => l.name === "ask-claude") || /^\[ask\]/i.test(i.title || "")));
        if (!waiting.length) return;
        const box = $("#pending"); box.appendChild(el("h4", "Waiting: Claude will answer these"));
        waiting.forEach((i) => { const a = el("a", `#${i.number} ${i.title.replace(/^\[Ask\]\s*/i, "")}`); a.href = i.html_url; a.target = "_blank"; a.rel = "noopener"; box.appendChild(a); });
        box.hidden = false;
      }).catch(() => {});
  }
})();
