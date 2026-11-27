export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Group conversations into Today / Yesterday / Previous 7 days / Older. */
export function groupConversations(conversations) {
  const groups = { Today: [], Yesterday: [], "Previous 7 days": [], Older: [] };
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const day = 24 * 60 * 60 * 1000;

  conversations.forEach((c) => {
    const t = new Date(c.updated_at || c.created_at).getTime();
    const diff = startOfToday.getTime() - t;
    if (t >= startOfToday.getTime()) groups.Today.push(c);
    else if (diff <= day) groups.Yesterday.push(c);
    else if (diff <= 7 * day) groups["Previous 7 days"].push(c);
    else groups.Older.push(c);
  });

  return Object.entries(groups).filter(([, items]) => items.length > 0);
}

/** Strip markdown so text-to-speech does not read out symbols. */
export function markdownToPlainText(md = "") {
  return md
    .replace(/```[\s\S]*?```/g, " code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/(\*\*|__|\*|_|~~)/g, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\n{2,}/g, ". ")
    .replace(/\s+/g, " ")
    .trim();
}

export const ACCEPTED_DOC_TYPES = [".pdf", ".docx", ".txt", ".md"];
export const MAX_UPLOAD_MB = 25;

export function validateDocument(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!ACCEPTED_DOC_TYPES.includes(ext))
    return `"${file.name}" is not supported. Use ${ACCEPTED_DOC_TYPES.join(", ")}.`;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024)
    return `"${file.name}" is larger than ${MAX_UPLOAD_MB} MB.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  return null;
}
