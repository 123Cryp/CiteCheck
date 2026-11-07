export const GEN = 10n ** 18n;
export const MIN_PAGE_LEN = 200;
export const MAX_CLAIM_LEN = 400;
export const MIN_PASSAGE_LEN = 20;
export const MAX_PASSAGE_LEN = 600;
export const MAX_URL_LEN = 300;
export const STATUSES = ["OPEN", "CHALLENGED", "ACCEPTED", "UPHELD", "REFUTED", "VOID"];

const PINNED = [
  /^https:\/\/raw\.githubusercontent\.com\/[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9._-]{1,100}\/[0-9a-f]{40}\/[A-Za-z0-9._~%\/-]{1,200}$/,
  /^https:\/\/arxiv\.org\/abs\/[0-9]{4}\.[0-9]{4,5}v[0-9]{1,3}$/,
  /^https:\/\/[a-z]{2,3}(?:-[a-z]{2,8}){0,2}\.wikipedia\.org\/w\/index\.php\?(?:title=[A-Za-z0-9_%().,'!:-]{1,200}&)?oldid=[0-9]{1,12}$/,
];

export const BLOCKED_CLAIM = /[<>{}`]|cc_|system prompt|ignore (?:all|previous|prior|the above)/i;

export function normText(s) {
  return String(s)
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201c\u201d]/g, '"')
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isPinned(url) {
  if (typeof url !== "string" || url.length === 0 || url.length > MAX_URL_LEN) return false;
  if (/\s/.test(url) || url.includes("#") || url.includes("@")) return false;
  if (/\/\.\.?(\/|$)/.test(url)) return false;
  return PINNED.some((r) => r.test(url));
}

export function sourceKind(url) {
  if (!isPinned(url)) return "";
  if (url.startsWith("https://raw.githubusercontent.com/")) return "github";
  if (url.startsWith("https://arxiv.org/")) return "arxiv";
  return "wikipedia";
}

export function validateClaim({ text, url, passage, bond }) {
  const t = normText(text ?? "");
  const p = normText(passage ?? "");
  const b = String(bond ?? "").trim();
  if (!/^[0-9]+$/.test(b) || BigInt(b) < 1n) return "Bond must be a whole number of GEN, at least 1.";
  if (!t || t.length > MAX_CLAIM_LEN) return "Statement must be 1 to 400 characters.";
  if (BLOCKED_CLAIM.test(t)) return "Statement contains characters or phrases reserved for the judge (< > { } ` cc_ and instruction-like phrases).";
  if (p.length < MIN_PASSAGE_LEN || p.length > MAX_PASSAGE_LEN) return "Quoted passage must be 20 to 600 characters.";
  if (!isPinned((url ?? "").trim())) return "Source URL is not one of the accepted pinned forms.";
  return "";
}

export function validateCounter(text) {
  const t = normText(text ?? "");
  if (t && (t.length < MIN_PASSAGE_LEN || t.length > MAX_PASSAGE_LEN)) return "Counter passage must be empty or 20 to 600 characters.";
  return "";
}

export function pinGithubUrl(link, sha) {
  const input = String(link ?? "").trim();
  const commit = String(sha ?? "").trim().toLowerCase();
  if (!input) return { error: "Paste a GitHub file link first." };
  let m = input.match(/^https:\/\/github\.com\/([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9._-]{1,100})\/blob\/([^\/?#]+)\/([^?#]+)$/);
  let owner;
  let repo;
  let ref;
  let path;
  if (m) {
    [, owner, repo, ref, path] = m;
  } else {
    m = input.match(/^https:\/\/raw\.githubusercontent\.com\/([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9._-]{1,100})\/([^\/?#]+)\/([^?#]+)$/);
    if (!m) return { error: "Expected a github.com/<owner>/<repo>/blob/<ref>/<path> or raw.githubusercontent.com link." };
    [, owner, repo, ref, path] = m;
  }
  let pin = "";
  if (/^[0-9a-f]{40}$/.test(ref)) pin = ref;
  else if (/^[0-9a-f]{40}$/.test(commit)) pin = commit;
  else return { error: "This link points to a branch or tag. Paste the full 40-character commit sha from the commit page." };
  const url = "https://raw.githubusercontent.com/" + owner + "/" + repo + "/" + pin + "/" + path;
  if (!isPinned(url)) return { error: "The resulting URL is not an accepted pinned form (check the path characters)." };
  return { url, usedSha: pin };
}

export function checkPassage(page, passage) {
  const body = normText(page ?? "");
  const quote = normText(passage ?? "");
  if (!quote) return { state: "empty", pageLength: body.length };
  const found = body.toLowerCase().includes(quote.toLowerCase());
  if (found) return { state: "found", pageLength: body.length };
  if (body.length < MIN_PAGE_LEN) return { state: "short", pageLength: body.length };
  return { state: "missing", pageLength: body.length };
}

export function describeCheck(result, who) {
  const subject = who || "The quoted passage";
  if (result.state === "found") return { kind: "ok", text: subject + " appears on the page (" + result.pageLength + " characters read). The validators will compare it in code the same way." };
  if (result.state === "missing") return { kind: "bad", text: subject + " was not found on the page. On chain this is decided in code as MISQUOTED and the challenger wins." };
  if (result.state === "short") return { kind: "bad", text: "The page returned only " + result.pageLength + " characters, which the contract treats as a possible error page (UNDETERMINED). Check the URL." };
  return { kind: "", text: "Nothing to check yet." };
}

export function computeStats(items, genUnit = GEN) {
  const counts = Object.fromEntries(STATUSES.map((s) => [s, 0]));
  let escrowed = 0n;
  for (const c of items) {
    if (c.status in counts) counts[c.status] += 1;
    const bond = BigInt(c.bond ?? 0);
    if (c.status === "OPEN") escrowed += bond;
    else if (c.status === "CHALLENGED") escrowed += bond * 2n;
  }
  const decided = counts.UPHELD + counts.REFUTED;
  const upheldRate = decided ? Math.round((counts.UPHELD * 100) / decided) : null;
  return { total: items.length, counts, escrowed, escrowedGen: Number(escrowed / genUnit), decided, upheldRate };
}

const BADGE_COLORS = { OPEN: "blue", CHALLENGED: "orange", ACCEPTED: "brightgreen", UPHELD: "brightgreen", REFUTED: "red", VOID: "lightgrey" };

export function badgeMarkdown(pageBase, id, status) {
  const color = BADGE_COLORS[status] || "lightgrey";
  const link = claimLink(pageBase, id);
  const img = "https://img.shields.io/badge/CiteCheck-" + encodeURIComponent(status) + "-" + color;
  return "[![CiteCheck claim " + id + ": " + status + "](" + img + ")](" + link + ")";
}

export function claimLink(siteBase, id) {
  const root = String(siteBase).replace(/#.*$/, "");
  return root + "#/claim/" + encodeURIComponent(id);
}

export function friendlyError(e) {
  const msg = String((e && (e.shortMessage || e.message)) || e || "");
  if (/user rejected|denied|cancel/i.test(msg)) return "The wallet request was cancelled.";
  if (/insufficient funds|insufficient balance/i.test(msg)) return "This account does not have enough GEN for the bond. Fund it and try again.";
  if (/failed to fetch|networkerror|network request failed/i.test(msg)) return "Network error while reaching GenLayer Studio. Check the connection and retry.";
  return msg || "Unknown error.";
}
