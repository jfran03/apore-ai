/** Keys that mark a JSON object as a tutor/grade protocol trailer. */
const PROTOCOL_TRAILER_KEYS = new Set([
  'question_closed',
  'correct',
  'feedback_regions',
  'help_request',
]);

function* iterJsonObjects(text: string): Generator<string> {
  for (let start = 0; start < text.length; start += 1) {
    if (text[start] !== '{') continue;
    let depth = 0;
    for (let i = start; i < text.length; i += 1) {
      const ch = text[i];
      if (ch === '{') depth += 1;
      else if (ch === '}') {
        depth -= 1;
        if (depth === 0) {
          const candidate = text.slice(start, i + 1);
          try {
            JSON.parse(candidate);
            yield candidate;
          } catch {
            // not valid JSON; keep scanning
          }
          break;
        }
      }
    }
  }
}

function findProtocolTrailer(text: string): string | null {
  let last: string | null = null;
  for (const candidate of iterJsonObjects(text)) {
    try {
      const parsed = JSON.parse(candidate) as unknown;
      if (
        parsed &&
        typeof parsed === 'object' &&
        !Array.isArray(parsed) &&
        Object.keys(parsed as object).some((key) => PROTOCOL_TRAILER_KEYS.has(key))
      ) {
        last = candidate;
      }
    } catch {
      // ignore
    }
  }
  return last;
}

/**
 * Strip tutor/grade protocol JSON trailers (and wrapping fences) from display text.
 * Learner-visible replies must not show `{"question_closed":...}` metadata.
 */
export function stripProtocolTrailer(text: string): string {
  let out = text.trim();
  if (!out) return out;

  // Whole-message fence unwrap (matches backend _strip_code_fence).
  const lines = out.split(/\r?\n/);
  if (lines[0]?.trim().startsWith('```')) {
    lines.shift();
    if (lines.length && lines[lines.length - 1]?.trim() === '```') {
      lines.pop();
    }
    out = lines.join('\n').trim();
  }

  const trailer = findProtocolTrailer(out);
  if (!trailer) return out.trim();

  const escaped = trailer.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const fenced = new RegExp('```(?:json)?\\s*\\n?\\s*' + escaped + '\\s*\\n?\\s*```', 'i');
  const openOnly = new RegExp('```(?:json)?\\s*\\n?\\s*' + escaped, 'i');
  if (fenced.test(out)) {
    out = out.replace(fenced, '');
  } else if (openOnly.test(out)) {
    out = out.replace(openOnly, '');
  } else {
    out = out.replace(trailer, '');
  }
  out = out.replace(/```(?:json)?\s*```/gi, '');
  return out.trim();
}
