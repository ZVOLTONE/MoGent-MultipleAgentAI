export function Bullets({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-2">
      {items.map((b, i) => (
        <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-[var(--color-ink-soft)]">
          <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[var(--color-ink-faint)]" />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}
