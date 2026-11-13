const $ = s => document.querySelector(s);

const ICONS = {
  phone: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>`,
  mail: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>`,
  send: `<svg class="lucide-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>`,
  copy: `<svg class="lucide-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`,
  edit: `<svg class="lucide-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>`,
  mapPin: `<svg class="lucide-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"></path><circle cx="12" cy="10" r="3"></circle></svg>`,
  star: `<svg class="lucide-icon star-icon" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`,
  globe: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path><path d="M2 12h20"></path></svg>`,
  instagram: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="20" x="2" y="2" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" x1="17.5" y1="6.5" y2="6.5"></line></svg>`,
  facebook: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"></path></svg>`,
  twitter: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"></path></svg>`,
  linkedin: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect width="4" height="12" x="2" y="9"></rect><circle cx="4" cy="4" r="2"></circle></svg>`,
  tiktok: `<svg class="lucide-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"></path></svg>`,
  whatsapp: `<svg class="lucide-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>`,
  external: `<svg class="lucide-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>`
};

const TABS = {
  nowebsite: ["No website", r => r.site_status === "no_website"],
  social_only: ["Social only", r => r.site_status === "social_only"],
  broken: ["Broken website", r => r.site_status === "broken"],
  working: ["Has Website (Pitch Upgrades)", r => r.site_status === "working"],
  all: ["All Leads", () => true]
};

const LABEL = {
  no_website: "No website",
  social_only: "Social only",
  broken: "Broken website",
  working: "Has Website"
};

let rows = [];
let tab = "nowebsite";
let timer = null;
let currentSettings = {};
let activeModalLeadId = null;
let toastTimer = null;
const contacted = JSON.parse(localStorage.getItem("contacted") || "{}");

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

function safeUrl(u) {
  if (!u) return "";
  try {
    const parsed = new URL(String(u));
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}

function hasSmtpConfigured() {
  const secrets = currentSettings.configured_secrets || {};
  const hasPass = Boolean(currentSettings.smtp_password || secrets.smtp_password);
  return Boolean(currentSettings.smtp_email && hasPass);
}

function showToast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

async function copyText(text, label = "Copied to clipboard!") {
  try {
    await navigator.clipboard.writeText(text);
    showToast(label);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    showToast(label);
  }
}

// Initialize Providers & Settings
Promise.all([
  fetch("/api/providers").then(r => r.json()),
  fetch("/api/settings").then(r => r.json())
])
  .then(([ps, sData]) => {
    $("#provider").innerHTML = ps.map(p => `<option value="${p.id}" data-key="${p.key}">${esc(p.label)}</option>`).join("");
    currentSettings = sData.settings || {};
    syncAutoSendPill(sData.sent_total || 0);
    syncForm();
    render();
  })
  .catch(err => {
    $("#status").textContent = "Failed to initialize: " + err.message;
  });

function syncAutoSendPill(sentTotal) {
  const on = Boolean(currentSettings.auto_send_email);
  $("#quickAutoSend").checked = on;
  $("#autoSendLabel").textContent = on
    ? (currentSettings.dry_run ? "Auto-Email: DRY-RUN" : "Auto-Email: ON")
    : "Auto-Email: OFF";
  if (typeof sentTotal === "number") {
    $("#sentLedgerCount").textContent = `${sentTotal} emails tracked in single-send deduplication ledger`;
  }
}

function syncForm() {
  const opt = $("#provider").selectedOptions[0];
  const needsKey = opt ? opt.dataset.key === "true" : false;
  $("#keyBox").hidden = !needsKey;
  $("#gridBox").hidden = $("#provider").value !== "google";
}

function view() {
  const q = ($("#q").value || "").trim().toLowerCase();
  const cf = $("#contactFilter").value;

  return rows
    .filter(TABS[tab][1])
    .filter(r => {
      if (cf === "has_email") return Boolean(r.email && !r.email_guessed);
      if (cf === "has_any_email") return Boolean(r.email);
      if (cf === "has_dm") return Boolean((r.dm_info && r.dm_info.dm_url) || r.phone || (r.socials && r.socials.length));
      if (cf === "unsent_email") {
        return Boolean(r.email && !r.email_guessed && !["sent", "simulated", "already_sent"].includes(r.email_status));
      }
      return true;
    })
    .filter(r => {
      if (!q) return true;
      const haystack = [
        r.name, r.category, r.address, r.email, r.phone, r.website,
        r.site_note, ...(r.audit_issues || []), r.outreach_subject
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    })
    .sort((a, b) => (b.lead_score || 0) - (a.lead_score || 0) || (b.reviews || 0) - (a.reviews || 0));
}

function buildMailtoHref(r) {
  const primary = (r.email || "").split(",")[0].trim();
  const subj = encodeURIComponent(r.outreach_subject || `Quick question for ${r.name}`);
  const body = encodeURIComponent(r.outreach_body || "");
  return `mailto:${primary}?subject=${subj}&body=${body}`;
}

function buildWhatsAppPitchHref(r) {
  const digits = (r.phone || "").replace(/\D/g, "");
  if (digits.length < 7) return "";
  const text = encodeURIComponent(r.outreach_dm || r.outreach_body || "");
  return `https://wa.me/${digits}?text=${text}`;
}

function render() {
  // Render Tab counts
  $("#tabs").innerHTML = Object.entries(TABS).map(([k, [l, f]]) => {
    const count = rows.filter(f).length;
    return `<button type="button" data-t="${k}" class="${k === tab ? "on" : ""}">${esc(l)} (${count})</button>`;
  }).join("");

  // Summary metrics in status panel
  const verifiedEmails = rows.filter(r => r.email && !r.email_guessed).length;
  const guessedEmails = rows.filter(r => r.email && r.email_guessed).length;
  const totalDms = rows.filter(r => (r.dm_info && r.dm_info.dm_url) || r.phone).length;
  const totalSent = rows.filter(r => ["sent", "simulated"].includes(r.email_status)).length;
  $("#statusStats").innerHTML = rows.length > 0
    ? `<span class="stat-pill">✉️ ${verifiedEmails} Verified Email${guessedEmails > 0 ? ` (+${guessedEmails} Suggested)` : ""}</span>
       <span class="stat-pill">💬 ${totalDms} with DM/WhatsApp</span>
       ${totalSent > 0 ? `<span class="stat-pill stat-sent">🚀 ${totalSent} Emailed</span>` : ""}`
    : "";

  const visible = view();
  if (visible.length === 0) {
    $("#rows").innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 36px 14px; color: var(--mute);">
      ${rows.length === 0
        ? "Enter a city and business type above, then click <strong>Find &amp; Enrich Leads</strong>."
        : "No leads match this tab or filter."}
    </td></tr>`;
    return;
  }

  $("#rows").innerHTML = visible.map(r => {
    const score = Number(r.lead_score || 60);
    const scoreClass = score >= 80 ? "score-hot" : score >= 65 ? "score-warm" : "score-ok";

    // Rating & Map
    const ratingHtml = r.rating
      ? `<span class="rating-val">${ICONS.star} ${esc(r.rating)}${r.reviews ? ` <small class="dim">(${esc(r.reviews)})</small>` : ""}</span>`
      : "";
    const safeMapHref = safeUrl(r.maps_url);
    const mapHtml = safeMapHref
      ? `<a href="${esc(safeMapHref)}" target="_blank" rel="noopener" class="map-inline-link">${ICONS.mapPin} Maps</a>`
      : "";

    // Phone & 1-Click WhatsApp Pitch
    const waPitchHref = buildWhatsAppPitchHref(r);
    const waBadge = waPitchHref
      ? `<a href="${esc(waPitchHref)}" target="_blank" rel="noopener" class="badge-wa" title="Open WhatsApp with tailored pitch pre-filled">${ICONS.whatsapp} WhatsApp Pitch</a>`
      : "";
    const phoneHtml = r.phone
      ? `<div class="contact-line"><a href="tel:${esc(r.phone)}" class="contact-item">${ICONS.phone} ${esc(r.phone)}</a>${waBadge}</div>`
      : "";

    // Social Links
    const socialLinks = (r.socials || []).map(s => {
      const safeSoc = safeUrl(s);
      if (!safeSoc) return "";
      let icon = ICONS.globe;
      let label = safeSoc.replace(/https?:\/\/(www\.)?/, "").split("/")[0];
      if (safeSoc.includes("instagram.com")) { icon = ICONS.instagram; label = "Instagram"; }
      else if (safeSoc.includes("facebook.com")) { icon = ICONS.facebook; label = "Facebook"; }
      else if (safeSoc.includes("twitter.com") || safeSoc.includes("x.com")) { icon = ICONS.twitter; label = "X"; }
      else if (safeSoc.includes("linkedin.com")) { icon = ICONS.linkedin; label = "LinkedIn"; }
      else if (safeSoc.includes("tiktok.com")) { icon = ICONS.tiktok; label = "TikTok"; }
      else if (safeSoc.includes("linktr.ee")) { icon = ICONS.globe; label = "Linktree"; }
      return `<a href="${esc(safeSoc)}" target="_blank" rel="noopener" class="social-pill">${icon} ${esc(label)}</a>`;
    }).join("");

    // Email & Dispatch Status
    let emailHtml = `<span class="dim">No email found — use Copy &amp; DM →</span>`;
    if (r.email) {
      const allMails = r.email.split(",").map(m => m.trim()).filter(Boolean);
      const primary = allMails[0];
      const secondary = allMails.slice(1);
      let statusBadge = "";
      if (r.email_status === "sent") {
        statusBadge = `<span class="email-badge sent" title="${esc(r.email_status_note)}">✓ Sent</span>`;
      } else if (r.email_status === "simulated") {
        statusBadge = `<span class="email-badge simulated" title="${esc(r.email_status_note)}">✓ Dry-Run Sent</span>`;
      } else if (r.email_status === "already_sent") {
        statusBadge = `<span class="email-badge already" title="${esc(r.email_status_note)}">Previously Sent</span>`;
      } else if (r.email_status === "error") {
        statusBadge = `<span class="email-badge err" title="${esc(r.email_status_note)}">SMTP Error</span>`;
      } else if (r.email_guessed || r.email_status === "guessed") {
        statusBadge = `<span class="email-badge guessed" title="${esc(r.email_status_note || "Suggested domain candidate — verify before sending")}">Suggested</span>`;
      }
      emailHtml = `<div class="email-block">
        <a href="${esc(buildMailtoHref(r))}" class="email-link" title="Open in mail client">${ICONS.mail} ${esc(primary)}</a>
        ${statusBadge}
        ${secondary.length > 0 ? `<span class="email-secondary">+${secondary.length} more: ${esc(secondary.join(", "))}</span>` : ""}
      </div>`;
    }

    // Website Status + Live Audit / What They Need
    const statusKey = LABEL[r.site_status] ? r.site_status : "no_website";
    const statusTag = `<span class="tag ${esc(statusKey)}">${esc(LABEL[r.site_status] || r.site_status)}</span>`;
    const safeSiteHref = safeUrl(r.website);
    const cleanUrl = safeSiteHref ? safeSiteHref.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "") : "";
    const siteUrlHtml = safeSiteHref
      ? `<a href="${esc(safeSiteHref)}" target="_blank" rel="noopener" class="site-link" title="${esc(safeSiteHref)}">${esc(cleanUrl.slice(0, 30))}${cleanUrl.length > 30 ? "…" : ""} ${ICONS.external}</a>`
      : "";
    const siteNoteHtml = r.site_note ? `<span class="site-note">${esc(r.site_note)}</span>` : "";

    const auditPills = (r.audit_issues || []).map(iss => `<span class="audit-pill">${esc(iss)}</span>`).join("");

    // Outreach Column: Pitch Snippet + Instant Action Buttons
    const dmInfo = r.dm_info || {};
    const hasEmail = Boolean(r.email);
    const isSent = ["sent", "simulated"].includes(r.email_status);

    const sendSmtpBtn = hasEmail
      ? `<button type="button" class="btn-mini ${isSent ? "btn-sent" : "btn-send-smtp"}" data-action="send-smtp" data-id="${esc(r.id)}" title="${isSent ? "Click to re-send via SMTP" : (r.email_guessed ? "Suggested unverified address — click to send manually via SMTP" : "Send tailored email immediately via SMTP")}">
          ${ICONS.send} ${isSent ? "Sent ✓" : "Send Email"}
        </button>
        <a href="${esc(buildMailtoHref(r))}" class="btn-mini btn-mailto" title="Open pre-filled email in your default Mail app">
          ${ICONS.mail} Mail App
        </a>`
      : "";

    let copyDmBtn = "";
    if (safeUrl(dmInfo.dm_url)) {
      const platLabel = dmInfo.platform || "DM";
      copyDmBtn = `<button type="button" class="btn-mini btn-copy-dm" data-action="copy-open-dm" data-id="${esc(r.id)}" title="Copies tailored DM message and opens ${esc(platLabel)} (${esc(dmInfo.handle)}) in a new tab">
        ${ICONS.copy} Copy &amp; Open ${esc(platLabel)}
      </button>`;
    }

    return `<tr class="${contacted[r.id] ? "row-contacted" : ""}">
      <td class="td-done">
        <input type="checkbox" data-id="${esc(r.id)}" ${contacted[r.id] ? "checked" : ""} aria-label="Mark contacted">
      </td>
      <td class="td-biz">
        <div class="biz-header">
          <span class="biz-name">${esc(r.name)}</span>
          <span class="score-badge ${scoreClass}" title="Lead Opportunity Score">${esc(score)}</span>
        </div>
        ${r.address ? `<span class="biz-meta">${esc(r.address)}</span>` : ""}
        <div class="biz-tags-row">
          ${r.category ? `<span class="category-tag">${esc(r.category)}</span>` : ""}
          ${ratingHtml}
          ${mapHtml}
        </div>
      </td>
      <td class="td-contacts">
        ${emailHtml}
        ${phoneHtml}
        ${socialLinks ? `<div class="socials-row">${socialLinks}</div>` : ""}
      </td>
      <td class="td-audit">
        <div class="site-wrap">
          <div class="site-top-line">${statusTag} ${siteUrlHtml}</div>
          ${siteNoteHtml}
          ${auditPills ? `<div class="audit-pills-wrap">${auditPills}</div>` : ""}
        </div>
      </td>
      <td class="td-outreach">
        <div class="outreach-box">
          <div class="outreach-preview" data-action="open-pitch" data-id="${esc(r.id)}" title="Click to view or edit full tailored writeup">
            <strong>${esc(r.outreach_subject || "Tailored Pitch")}</strong>
            <p>${esc((r.outreach_dm || r.outreach_body || "").slice(0, 115))}…</p>
          </div>
          <div class="outreach-actions">
            ${sendSmtpBtn}
            ${copyDmBtn}
            <button type="button" class="btn-mini btn-ghost" data-action="copy-pitch" data-id="${esc(r.id)}" title="Copy tailored message to clipboard">
              ${ICONS.copy} Copy
            </button>
            <button type="button" class="btn-mini btn-ghost" data-action="open-pitch" data-id="${esc(r.id)}" title="Customize pitch angle or rewrite">
              ${ICONS.edit} Pitch / Edit
            </button>
          </div>
        </div>
      </td>
    </tr>`;
  }).join("");
}

// Event Listeners
$("#provider").onchange = syncForm;
$("#q").oninput = render;
$("#contactFilter").onchange = render;

$("#tabs").onclick = e => {
  const btn = e.target.closest("button");
  if (btn && btn.dataset.t) {
    tab = btn.dataset.t;
    render();
  }
};

// Quick Auto-Send Toggle in Header
$("#quickAutoSend").onchange = async e => {
  const enabled = e.target.checked;
  if (enabled && !hasSmtpConfigured() && !currentSettings.dry_run) {
    showToast("Configure your SMTP Email & App Password (or enable Dry-Run) to auto-send emails.");
    openSettingsModal();
    e.target.checked = false;
    return;
  }
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({auto_send_email: enabled})
    });
    const data = await res.json();
    currentSettings = data.settings || currentSettings;
    syncAutoSendPill(data.sent_total);
    showToast(enabled ? "Auto-Email enabled for new leads!" : "Auto-Email paused.");
  } catch (err) {
    showToast("Failed to update setting: " + err.message);
  }
};

// Table Row Delegated Actions
$("#rows").onchange = e => {
  if (e.target.type === "checkbox" && e.target.dataset.id) {
    contacted[e.target.dataset.id] = e.target.checked;
    localStorage.setItem("contacted", JSON.stringify(contacted));
    render();
  }
};

$("#rows").onclick = async e => {
  const actionEl = e.target.closest("[data-action]");
  if (!actionEl) return;
  const action = actionEl.dataset.action;
  const id = actionEl.dataset.id;
  const lead = rows.find(r => r.id === id);
  if (!lead) return;

  if (action === "open-pitch") {
    openPitchModal(lead);
  } else if (action === "copy-pitch") {
    const textToCopy = lead.email ? lead.outreach_body : (lead.outreach_dm || lead.outreach_body);
    await copyText(textToCopy, `Copied pitch for ${lead.name}!`);
  } else if (action === "copy-open-dm") {
    const dmText = lead.outreach_dm || lead.outreach_body;
    await copyText(dmText, `Copied DM for ${lead.name}! Opening ${lead.dm_info?.platform || "profile"}...`);
    contacted[lead.id] = true;
    localStorage.setItem("contacted", JSON.stringify(contacted));
    render();
    const dmUrl = safeUrl(lead.dm_info?.dm_url);
    if (dmUrl) {
      window.open(dmUrl, "_blank", "noopener");
    }
  } else if (action === "send-smtp") {
    await sendLeadEmailViaSmtp(lead, actionEl);
  }
};

async function sendLeadEmailViaSmtp(lead, btnEl = null) {
  if (!lead.email) {
    showToast("No email address for this business.");
    return {ok: false, status: "no_email"};
  }
  const origHtml = btnEl ? btnEl.innerHTML : "";
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "Sending...";
  }
  try {
    const res = await fetch("/api/send-email", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        email: lead.email,
        subject: lead.outreach_subject,
        body: lead.outreach_body,
        name: lead.name,
        force: true
      })
    });
    const data = await res.json();
    if (data.ok) {
      lead.email_status = data.status;
      lead.email_status_note = data.message;
      contacted[lead.id] = true;
      localStorage.setItem("contacted", JSON.stringify(contacted));
      showToast(`✓ ${data.message}`);
      render();
      return {ok: true, status: data.status};
    } else {
      lead.email_status = "error";
      lead.email_status_note = data.message;
      showToast(data.message || "Failed to send email");
      if (data.status === "unconfigured") openSettingsModal();
      render();
      return {ok: false, status: data.status || "error"};
    }
  } catch (err) {
    showToast("Error sending email: " + err.message);
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = origHtml;
    }
    return {ok: false, status: "network_error"};
  }
}

// Bulk Send All Unsent Verified Emails
$("#sendAllBtn").onclick = async () => {
  const unsentLeads = view().filter(
    r => r.email && !r.email_guessed && !["sent", "simulated", "already_sent"].includes(r.email_status)
  );
  if (unsentLeads.length === 0) {
    showToast("No unsent verified email leads in the current view.");
    return;
  }
  if (!hasSmtpConfigured() && !currentSettings.dry_run) {
    showToast("Configure your SMTP credentials (or enable Dry-Run) in Settings first.");
    openSettingsModal();
    return;
  }

  $("#sendAllBtn").disabled = true;
  let sentCount = 0;
  for (let i = 0; i < unsentLeads.length; i++) {
    $("#sendAllText").textContent = `Sending ${i + 1}/${unsentLeads.length}...`;
    const res = await sendLeadEmailViaSmtp(unsentLeads[i]);
    if (res.ok) {
      sentCount++;
    } else if (res.status === "unconfigured") {
      break;
    }
  }
  $("#sendAllText").textContent = "Email All Unsent";
  $("#sendAllBtn").disabled = false;
  showToast(`Finished! Dispatched ${sentCount} tailored outreach emails.`);
};

// Pitch Modal Logic
function openPitchModal(lead) {
  activeModalLeadId = lead.id;
  $("#pitchModalTitle").textContent = `${lead.name} (${lead.city || ""})`;
  $("#pitchModalStatus").textContent = `${LABEL[lead.site_status] || lead.site_status} • Score ${lead.lead_score || 60}/100`;
  $("#pitchAngleSelect").value = currentSettings.pitch_angle || "auto";

  const issues = lead.audit_issues || [];
  $("#pitchAuditSummary").innerHTML = issues.length > 0
    ? `<strong>Detected Opportunities / Audit Gaps:</strong> ` + issues.map(i => `<span class="audit-pill">${esc(i)}</span>`).join(" ")
    : "";

  $("#pitchSubjectInput").value = lead.outreach_subject || "";
  $("#pitchBodyInput").value = lead.outreach_body || "";
  $("#pitchDmInput").value = lead.outreach_dm || "";

  syncModalFooterLinks(lead);
  $("#pitchModal").hidden = false;
}

function syncModalFooterLinks(lead) {
  lead.outreach_subject = $("#pitchSubjectInput").value;
  lead.outreach_body = $("#pitchBodyInput").value;
  lead.outreach_dm = $("#pitchDmInput").value;

  $("#modalMailtoBtn").href = buildMailtoHref(lead);
  $("#modalMailtoBtn").hidden = !lead.email;
  $("#modalSendSmtpBtn").hidden = !lead.email;

  const waHref = buildWhatsAppPitchHref(lead);
  const waBtn = $("#modalWaBtn");
  if (waHref) {
    waBtn.href = waHref;
    waBtn.hidden = false;
  } else {
    waBtn.hidden = true;
  }

  const dmBtn = $("#modalCopyOpenDmBtn");
  if (lead.dm_info && safeUrl(lead.dm_info.dm_url)) {
    dmBtn.textContent = `Copy & Open ${lead.dm_info.platform} DM`;
    dmBtn.hidden = false;
  } else {
    dmBtn.hidden = true;
  }
}

$("#pitchSubjectInput").oninput = () => {
  const lead = rows.find(r => r.id === activeModalLeadId);
  if (lead) { syncModalFooterLinks(lead); render(); }
};
$("#pitchBodyInput").oninput = () => {
  const lead = rows.find(r => r.id === activeModalLeadId);
  if (lead) { syncModalFooterLinks(lead); render(); }
};
$("#pitchDmInput").oninput = () => {
  const lead = rows.find(r => r.id === activeModalLeadId);
  if (lead) { syncModalFooterLinks(lead); render(); }
};

async function triggerPitchRegen(useAi = false) {
  const lead = rows.find(r => r.id === activeModalLeadId);
  if (!lead) return;
  const angle = $("#pitchAngleSelect").value;
  const btn = useAi ? $("#aiRewriteBtn") : $("#regenPitchBtn");
  const prevText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Generating...";
  try {
    const res = await fetch("/api/regenerate-pitch", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({lead, angle, use_ai: useAi})
    });
    const data = await res.json();
    if (data.ok) {
      $("#pitchSubjectInput").value = data.subject;
      $("#pitchBodyInput").value = data.body;
      $("#pitchDmInput").value = data.dm;
      syncModalFooterLinks(lead);
      render();
      showToast(useAi ? "Pitch polished!" : "Pitch updated for selected angle!");
    }
  } catch (err) {
    showToast("Failed to regenerate pitch: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = prevText;
  }
}

$("#pitchAngleSelect").onchange = () => triggerPitchRegen(false);
$("#regenPitchBtn").onclick = () => triggerPitchRegen(false);
$("#aiRewriteBtn").onclick = () => triggerPitchRegen(true);

$("#modalCopyEmailBtn").onclick = () => copyText($("#pitchBodyInput").value, "Copied email writeup!");
$("#modalCopyDmBtn").onclick = () => copyText($("#pitchDmInput").value, "Copied short DM message!");

$("#modalCopyOpenDmBtn").onclick = async () => {
  const lead = rows.find(r => r.id === activeModalLeadId);
  const dmUrl = safeUrl(lead?.dm_info?.dm_url);
  if (!lead || !dmUrl) return;
  await copyText($("#pitchDmInput").value, `Copied DM! Opening ${lead.dm_info.platform}...`);
  contacted[lead.id] = true;
  localStorage.setItem("contacted", JSON.stringify(contacted));
  render();
  window.open(dmUrl, "_blank", "noopener");
};

$("#modalSendSmtpBtn").onclick = async () => {
  const lead = rows.find(r => r.id === activeModalLeadId);
  if (!lead) return;
  syncModalFooterLinks(lead);
  await sendLeadEmailViaSmtp(lead, $("#modalSendSmtpBtn"));
  $("#modalSendSmtpBtn").textContent = "Send Email Now";
  $("#modalSendSmtpBtn").disabled = false;
};

$("#closePitchModal").onclick = () => { $("#pitchModal").hidden = true; };

// Settings Modal Logic
function openSettingsModal() {
  const s = currentSettings;
  const secrets = s.configured_secrets || {};
  $("#s_sender_name").value = s.sender_name || "";
  $("#s_sender_company").value = s.sender_company || "";
  $("#s_sender_portfolio").value = s.sender_portfolio || "";
  $("#s_sender_phone").value = s.sender_phone || "";
  $("#s_pitch_angle").value = s.pitch_angle || "auto";
  $("#s_custom_offer").value = s.custom_offer || "";
  $("#s_smtp_email").value = s.smtp_email || "";
  $("#s_smtp_password").value = "";
  $("#s_smtp_password").placeholder = secrets.smtp_password ? "Saved — leave blank to keep" : "••••••••••••••••";
  $("#s_smtp_host").value = s.smtp_host || "smtp.gmail.com";
  $("#s_smtp_port").value = s.smtp_port || 465;
  $("#s_auto_send_email").checked = Boolean(s.auto_send_email);
  $("#s_dry_run").checked = Boolean(s.dry_run);
  $("#s_hunter_api_key").value = "";
  $("#s_hunter_api_key").placeholder = secrets.hunter_api_key ? "Saved — leave blank to keep" : "Optional";
  $("#s_gemini_api_key").value = "";
  $("#s_gemini_api_key").placeholder = secrets.gemini_api_key ? "Saved — leave blank to keep" : "AIzaSy... (Optional)";
  $("#s_groq_api_key").value = "";
  $("#s_groq_api_key").placeholder = secrets.groq_api_key ? "Saved — leave blank to keep" : "gsk_... (Optional)";
  $("#smtpTestStatus").textContent = "";
  $("#settingsModal").hidden = false;
}

function collectSettingsForm() {
  return {
    sender_name: $("#s_sender_name").value.trim(),
    sender_company: $("#s_sender_company").value.trim(),
    sender_portfolio: $("#s_sender_portfolio").value.trim(),
    sender_phone: $("#s_sender_phone").value.trim(),
    pitch_angle: $("#s_pitch_angle").value,
    custom_offer: $("#s_custom_offer").value.trim(),
    smtp_email: $("#s_smtp_email").value.trim(),
    smtp_password: $("#s_smtp_password").value.trim(),
    smtp_host: $("#s_smtp_host").value.trim() || "smtp.gmail.com",
    smtp_port: parseInt($("#s_smtp_port").value, 10) || 465,
    auto_send_email: $("#s_auto_send_email").checked,
    dry_run: $("#s_dry_run").checked,
    hunter_api_key: $("#s_hunter_api_key").value.trim(),
    gemini_api_key: $("#s_gemini_api_key").value.trim(),
    groq_api_key: $("#s_groq_api_key").value.trim()
  };
}

$("#openSettingsBtn").onclick = openSettingsModal;
$("#closeSettingsModal").onclick = () => { $("#settingsModal").hidden = true; };
$("#cancelSettingsBtn").onclick = () => { $("#settingsModal").hidden = true; };

$("#settingsForm").onsubmit = async e => {
  e.preventDefault();
  const payload = collectSettingsForm();
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    currentSettings = data.settings || payload;
    syncAutoSendPill(data.sent_total);
    $("#settingsModal").hidden = true;
    showToast("Settings saved!");
  } catch (err) {
    showToast("Error saving settings: " + err.message);
  }
};

$("#testSmtpBtn").onclick = async () => {
  const settings = collectSettingsForm();
  $("#smtpTestStatus").textContent = "Testing connection...";
  $("#testSmtpBtn").disabled = true;
  try {
    const res = await fetch("/api/test-smtp", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({settings, to: settings.smtp_email})
    });
    const data = await res.json();
    $("#smtpTestStatus").textContent = data.message || (data.ok ? "Connected!" : "Failed");
    $("#smtpTestStatus").style.color = data.ok ? "var(--ok-text)" : "var(--bad-text)";
    const sRes = await fetch("/api/settings");
    if (sRes.ok) {
      const sData = await sRes.json();
      currentSettings = sData.settings || currentSettings;
      syncAutoSendPill(sData.sent_total);
    }
  } catch (err) {
    $("#smtpTestStatus").textContent = "Error: " + err.message;
  } finally {
    $("#testSmtpBtn").disabled = false;
  }
};

// Close modals on backdrop click
window.onclick = e => {
  if (e.target === $("#pitchModal")) $("#pitchModal").hidden = true;
  if (e.target === $("#settingsModal")) $("#settingsModal").hidden = true;
};

// Search Form Submission
$("#f").onsubmit = async e => {
  e.preventDefault();
  clearInterval(timer);
  rows = [];
  render();
  $("#go").disabled = true;
  $("#status").textContent = "Initializing search & deep contact hunter...";

  const body = {
    provider: $("#provider").value,
    key: $("#key").value,
    city: $("#city").value,
    category: $("#cat").value,
    grid: $("#grid").value
  };

  try {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const startData = await res.json();
    if (!res.ok || !startData.id) {
      throw new Error(startData.error || "Failed to start search");
    }
    const {id} = startData;

    timer = setInterval(async () => {
      try {
        const pollRes = await fetch(`/api/job/${id}?since=${rows.length}`);
        const j = await pollRes.json();
        if (!pollRes.ok) {
          throw new Error(j.error || "Failed to poll job");
        }
        if (j.results && j.results.length > 0) {
          rows.push(...j.results);
          render();
        }
        const sentNote = j.sent_count > 0 ? ` • ${j.sent_count} auto-emailed` : "";
        $("#status").textContent = j.error
          ? "Error: " + j.error
          : `${j.msg}: ${j.found} discovered, ${rows.length} audited & pitched${sentNote}`;

        if (j.done) {
          clearInterval(timer);
          $("#go").disabled = false;
        }
      } catch (pollErr) {
        clearInterval(timer);
        $("#go").disabled = false;
        $("#status").textContent = "Error checking progress: " + pollErr.message;
      }
    }, 1200);
  } catch (err) {
    $("#status").textContent = "Failed to start search: " + err.message;
    $("#go").disabled = false;
  }
};

// CSV Export with full outreach intelligence
$("#csv").onclick = () => {
  const currentRows = view();
  if (currentRows.length === 0) {
    showToast("No leads to export in the current view.");
    return;
  }
  const cols = [
    "name", "category", "address", "email", "email_verified", "phone", "socials", "website",
    "site_status", "site_note", "audit_issues", "lead_score", "rating",
    "reviews", "maps_url", "email_status", "outreach_subject", "outreach_body", "outreach_dm"
  ];
  const headerRow = cols.join(",");
  const dataRows = currentRows.map(r => {
    return cols.map(c => {
      let val = r[c] ?? "";
      if (Array.isArray(val)) val = val.join(" | ");
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(",");
  });

  const csvContent = [headerRow, ...dataRows].join("\n");
  const blob = new Blob([csvContent], {type: "text/csv;charset=utf-8;"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `leads-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
};
