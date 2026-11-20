(() => {
  "use strict";
  const cfg = Object.assign({ owner: "", repo: "", siteTitle: "Rule Forge" }, window.RULE_FORGE || {});

  // Detect owner/repo from https://<owner>.github.io/<repo>/
  if (!cfg.owner && location.hostname.endsWith(".github.io")) {
    cfg.owner = location.hostname.split(".")[0];
    cfg.repo = cfg.repo || location.pathname.split("/").filter(Boolean)[0] || location.hostname;
  }
  const repoUrl = cfg.owner && cfg.repo ? `https://github.com/${cfg.owner}/${cfg.repo}` : "";

  const $ = (sel, el = document) => el.querySelector(sel);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };

  document.title = cfg.siteTitle;
  $("#site-title").textContent = cfg.siteTitle;
  if (repoUrl) $("#repo-link").href = repoUrl; else $("#repo-link").hidden = true;

  // ---------- Request form -> pre-filled GitHub issue ----------
  $("#request-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const err = $("#form-error");
    const data = Object.fromEntries(new FormData(e.target).entries());
    const fail = (msg) => { err.textContent = msg; err.hidden = false; };
    err.hidden = true;

    if (!repoUrl) return fail("Repository not configured. Set owner and repo in docs/config.js.");
    if (!data.title.trim() || !data.requirement.trim()) return fail("Add a rule title and a requirement.");

    const params = new URLSearchParams({ template: "rule-request.yml", title: `[Rule] ${data.title.trim()}` });
    for (const key of ["language", "data_source", "requirement", "logic", "mitre", "severity", "samples"]) {
      if (data[key] && data[key].trim()) params.set(key, data[key].trim());
    }
    const url = `${repoUrl}/issues/new?${params}`;
    if (url.length > 8000) return fail("The request is too long for a link. Shorten the sample logs, or paste them into the issue after it opens.");
    window.open(url, "_blank", "noopener");
  });

  // ---------- Rules ----------
  const list = $("#rule-list");
  const tpl = $("#rule-tpl");
  let rules = [];

  const fillList = (ul, items) => {
    const arr = (items || []).filter(Boolean);
    if (!arr.length) { ul.closest("div").hidden = true; return; }
    arr.forEach((t) => ul.appendChild(el("li", t)));
  };

  const copyButton = (btn, text) => btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(text); } catch {
      const ta = el("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
    }
    btn.textContent = "Copied"; btn.classList.add("done");
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("done"); }, 1500);
  });

  function renderRule(rec) {
    const r = rec.rule || {};
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.id = `rule-${rec.issue}`;
    const sev = $(".sev", node); sev.textContent = r.severity || "—"; sev.classList.add(r.severity || "Informational");
    $(".rule-title", node).textContent = r.rule_name || rec.title;
    $(".lang", node).textContent = (r.query_language || "").split(" ")[0] || "?";
    $(".summary", node).textContent = r.summary || "";
    $(".query", node).textContent = r.query || "";
    copyButton($(".copy", node), r.query || "");

    const variants = $(".variants", node);
    (r.variants || []).forEach((v) => {
      variants.appendChild(el("h4", `Variant: ${v.name}`));
      const wrap = el("div", null, "code-wrap");
      const btn = el("button", "Copy", "copy"); btn.type = "button"; copyButton(btn, v.query);
      const pre = el("pre"); pre.appendChild(el("code", v.query));
      wrap.append(btn, pre); variants.appendChild(wrap);
    });

    fillList($(".logic", node), r.logic_explanation);
    fillList($(".assumptions", node), r.assumptions);
    fillList($(".fps", node), r.false_positives);
    fillList($(".tuning", node), r.tuning);
    if (r.testing) $(".testing", node).textContent = r.testing; else $(".testing-wrap", node).hidden = true;

    const labels = { language: "Language", data_source: "Data source", requirement: "Requirement", logic: "Logic", mitre: "MITRE", severity: "Severity", samples: "Samples" };
    const dl = $(".req-list", node);
    for (const [k, label] of Object.entries(labels)) {
      const v = (rec.request || {})[k];
      if (v) { dl.appendChild(el("dt", label)); dl.appendChild(el("dd", v)); }
    }

    const meta = $(".meta", node);
    (r.mitre || []).forEach((m) => { const s = el("span", m.id, "mitre"); s.title = m.name; meta.appendChild(s); });
    if (rec.issue_url) { const a = el("a", `Issue #${rec.issue}`); a.href = rec.issue_url; a.target = "_blank"; a.rel = "noopener"; meta.appendChild(a); }
    if (rec.requested_by) meta.appendChild(el("span", `by @${rec.requested_by}`));
    meta.appendChild(el("span", `rev ${rec.revision} · ${new Date(rec.updated_at).toLocaleString()}`));

    const head = $(".rule-head", node), body = $(".rule-body", node);
    head.addEventListener("click", () => {
      const open = head.getAttribute("aria-expanded") !== "true";
      head.setAttribute("aria-expanded", String(open)); body.hidden = !open;
    });
    return node;
  }

  function haystack(rec) {
    const r = rec.rule || {};
    return [rec.title, r.rule_name, r.summary, r.query, r.query_language, (r.mitre || []).map((m) => `${m.id} ${m.name}`).join(" "), rec.request && rec.request.data_source]
      .join(" ").toLowerCase();
  }

  function render() {
    const q = $("#search").value.trim().toLowerCase();
    const lang = $("#lang-filter").value;
    list.replaceChildren();
    const shown = rules.filter((rec) => (!lang || ((rec.rule || {}).query_language || "").startsWith(lang)) && (!q || haystack(rec).includes(q)));
    shown.forEach((rec) => list.appendChild(renderRule(rec)));
    $("#rule-count").textContent = rules.length ? `(${shown.length}${shown.length !== rules.length ? ` of ${rules.length}` : ""})` : "";
    $("#empty").hidden = rules.length > 0;
    openFromHash();
  }

  function openFromHash() {
    const m = location.hash.match(/^#rule-(\d+)$/);
    if (!m) return;
    const node = document.getElementById(`rule-${m[1]}`);
    if (node) { $(".rule-head", node).setAttribute("aria-expanded", "true"); $(".rule-body", node).hidden = false; node.scrollIntoView({ block: "start" }); }
  }
  window.addEventListener("hashchange", openFromHash);

  $("#search").addEventListener("input", render);
  $("#lang-filter").addEventListener("change", render);

  fetch(`data/rules.json?t=${Date.now()}`)
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => [])
    .then((data) => {
      rules = Array.isArray(data) ? data : [];
      const langs = [...new Set(rules.map((rec) => ((rec.rule || {}).query_language || "").split(" ")[0]).filter(Boolean))].sort();
      langs.forEach((l) => { const o = el("option", l); o.value = l; $("#lang-filter").appendChild(o); });
      render();
      loadPending();
    });

  // Open rule-request issues without a generated rule yet = "Claude is working on it".
  function loadPending() {
    if (!repoUrl) return;
    fetch(`https://api.github.com/repos/${cfg.owner}/${cfg.repo}/issues?labels=rule-request&state=open&per_page=20`)
      .then((r) => (r.ok ? r.json() : []))
      .then((issues) => {
        const done = new Set(rules.map((r) => r.issue));
        const waiting = issues.filter((i) => !i.pull_request && !done.has(i.number));
        if (!waiting.length) return;
        const box = $("#pending");
        box.appendChild(el("h4", "In progress: Claude is writing these rules"));
        waiting.forEach((i) => { const a = el("a", `#${i.number} ${i.title.replace(/^\[Rule\]\s*/, "")}`); a.href = i.html_url; a.target = "_blank"; a.rel = "noopener"; box.appendChild(a); });
        box.hidden = false;
      })
      .catch(() => {});
  }
})();
