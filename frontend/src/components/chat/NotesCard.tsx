export function NotesCard({ items }: { items: string[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="rounded-2xl bg-white/70 p-3 text-xs">
      <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Notes</div>
      <div className="space-y-1">
        {items.map((item, index) => (
          <div key={`${item}-${index}`}>{item}</div>
        ))}
      </div>
    </div>
  );
}
