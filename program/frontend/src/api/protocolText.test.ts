import { describe, expect, it } from 'vitest';
import { stripProtocolTrailer } from './protocolText';

describe('stripProtocolTrailer', () => {
  it('removes a raw grade trailer after prose', () => {
    const out = stripProtocolTrailer(
      'Correct. Nice work.\n{"question_closed": true, "correct": "yes", "feedback_regions": []}',
    );
    expect(out).toBe('Correct. Nice work.');
  });

  it('removes a fenced trailer even when prose has empty-set braces', () => {
    const out = stripProtocolTrailer(
      'Correct. The empty set is {}.\n\n```json\n{"question_closed": true, "correct": "yes", "feedback_regions": []}\n```',
    );
    expect(out).toBe('Correct. The empty set is {}.');
    expect(out).not.toContain('question_closed');
  });

  it('returns empty when the message is only a trailer', () => {
    expect(
      stripProtocolTrailer('{"question_closed": true, "correct": "yes", "feedback_regions": []}'),
    ).toBe('');
  });
});
