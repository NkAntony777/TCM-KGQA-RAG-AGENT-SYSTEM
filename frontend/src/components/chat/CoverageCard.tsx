import type { EvidenceBundle } from "@/lib/api";

export function CoverageCard({ bundle }: { bundle?: EvidenceBundle }) {
  const coverage = bundle?.coverage;
  if (!bundle || !coverage) {
    return null;
  }

  const gaps = Array.isArray(coverage.gaps) ? coverage.gaps.map((item) => String(item)) : [];
  const selectedCards = bundle.selected_evidence_cards ?? [];
  const selection = bundle.evidence_selection;

  return (
    <div className="rounded-2xl bg-white/70 p-3 text-xs">
      <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Coverage</div>
      <div className="grid gap-2 md:grid-cols-2">
        <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3">
          <div>factual_count: {coverage.factual_count ?? 0}</div>
          <div>case_count: {coverage.case_count ?? 0}</div>
          <div>evidence_path_count: {coverage.evidence_path_count ?? 0}</div>
          <div>sufficient: {coverage.sufficient ? "yes" : "no"}</div>
        </div>
        <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3">
          <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Remaining Gaps</div>
          <div>{gaps.length ? gaps.join(" / ") : "none"}</div>
        </div>
      </div>
      {!!selectedCards.length && (
        <div className="mt-2 rounded-2xl bg-[rgba(15,139,141,0.08)] p-3">
          <div className="mb-2 font-medium text-[var(--color-ink)]">
            Selected Evidence · {selectedCards.length}
          </div>
          {selection?.missing_facets?.length ? (
            <div className="mb-2 text-[var(--color-ember)]">
              missing: {selection.missing_facets.join(" / ")}
            </div>
          ) : null}
          <div className="space-y-2">
            {selectedCards.slice(0, 6).map((card, index) => (
              <div className="rounded-2xl bg-white/75 p-2" key={`${card.facet}-${card.claim}-${index}`}>
                <div className="font-medium text-[var(--color-ink)]">
                  {card.facet_label ?? card.facet ?? "evidence"} · {card.claim ?? ""}
                </div>
                <div className="mt-1 text-[var(--color-ink-soft)]">
                  {card.source_label ?? "unknown"}{card.why_selected ? ` · ${card.why_selected}` : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
