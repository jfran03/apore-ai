export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function isValidEduEmail(raw: string): boolean {
  const email = normalizeEmail(raw);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return false;
  return email.endsWith(".edu");
}

export function eduEmailError(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return "Enter your university email.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(trimmed))) {
    return "Enter a valid email address.";
  }
  if (!isValidEduEmail(trimmed)) {
    return "Use a .edu email address to join the waitlist.";
  }
  return null;
}
