export function TutorGeneratingRow() {
  return (
    <div
      className="tutor-chat__generating"
      role="status"
      aria-live="polite"
      aria-label="Apore is generating a response"
    >
      <span className="tutor-chat__generating-label">Generating</span>
      <span className="tutor-chat__generating-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}
