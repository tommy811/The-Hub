import Link from "next/link";

const CLASS_ORDER = [
  "monetization",
  "aggregator",
  "affiliate",
  "commerce",
  "content",
  "professional",
  "messaging",
  "social",
  "unknown",
  "other",
];

const CLASS_LABEL: Record<string, string> = {
  monetization: "Monetization",
  aggregator: "Link-in-Bio",
  affiliate: "Affiliate",
  commerce: "Commerce",
  content: "Content",
  professional: "Professional",
  messaging: "Messaging",
  social: "Social",
  unknown: "Unclassified",
  other: "Other",
};

export type Destination = {
  canonical_url: string;
  destination_class: string;
  raw_text: string | null;
  harvest_method: string | null;
  harvested_at: string | null;
};

export function CreatorDestinations({
  destinations,
}: {
  destinations: Destination[];
}) {
  if (destinations.length === 0) {
    return null;
  }

  const grouped: Record<string, Destination[]> = {};
  for (const d of destinations) {
    const cls = d.destination_class || "unknown";
    (grouped[cls] ||= []).push(d);
  }

  // Within each class, sort by quality signals:
  // 1. Has raw_text (anchor/button label) before bare URLs
  // 2. Shorter path (likely the canonical destination, not a sub-page)
  // 3. Newest harvested_at first
  for (const cls of Object.keys(grouped)) {
    grouped[cls].sort((a, b) => {
      const aHasText = a.raw_text ? 1 : 0;
      const bHasText = b.raw_text ? 1 : 0;
      if (aHasText !== bHasText) return bHasText - aHasText;

      const aPath = (() => { try { return new URL(a.canonical_url).pathname.length; } catch { return 999; } })();
      const bPath = (() => { try { return new URL(b.canonical_url).pathname.length; } catch { return 999; } })();
      if (aPath !== bPath) return aPath - bPath;

      const aTime = a.harvested_at ? Date.parse(a.harvested_at) : 0;
      const bTime = b.harvested_at ? Date.parse(b.harvested_at) : 0;
      return bTime - aTime;
    });
  }

  return (
    <div className="space-y-5">
      <p className="text-xs text-white/50 -mt-1 mb-2">
        Every URL the discovery pipeline harvested for this creator&apos;s network,
        grouped by class.
      </p>

      <div className="space-y-5">
        {CLASS_ORDER.filter((c) => grouped[c]?.length).map((cls) => (
          <div key={cls}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-white/60">
              {CLASS_LABEL[cls] ?? cls} ({grouped[cls].length})
            </h3>
            <ul className="space-y-1">
              {grouped[cls].map((d) => (
                <li
                  key={d.canonical_url}
                  className="flex flex-wrap items-baseline gap-2 text-sm"
                >
                  <Link
                    href={d.canonical_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-white/80 hover:text-violet-300 break-all"
                  >
                    {d.raw_text || d.canonical_url}
                  </Link>
                  {d.raw_text && (
                    <span className="text-xs text-white/40 break-all">
                      {d.canonical_url}
                    </span>
                  )}
                  {d.harvest_method === "headless" && (
                    <span
                      title="Captured via headless browser (sensitive-content gate)"
                      className="ml-1 rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-violet-300"
                    >
                      gated
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CreatorDestinations;
