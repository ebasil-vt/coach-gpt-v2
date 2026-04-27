// Shared template for coach notes — used by both /notes (Notes tab) and
// /new-game (Coach Notes section). Notes saved with these section markers
// can be loaded into New Game's 5 fields cleanly.
//
// Section order matches New Game's Coach Notes layout exactly.

export type NoteSections = {
  whatTheyRan: string;
  oppTendencies: string;
  whatWorked: string;
  whatDidnt: string;
  extra: string;
};

export const SECTION_DEFS: {
  key: keyof NoteSections;
  heading: string;
  hint: string;
  placeholder: string;
  accent?: string;
}[] = [
  {
    key: "whatTheyRan",
    heading: "What did they run?",
    hint: "Defense, offense, presses",
    placeholder:
      "2-3 zone\nTriangle offense\n3-2 press\nPress break: pass to corner",
  },
  {
    key: "oppTendencies",
    heading: "Opponent player tendencies",
    hint: "One per player, with jersey #",
    placeholder:
      "#1 can shoot, scored most\n#10 can't handle pressure\n#7 best player, boards\n#13 drives, make him shoot",
  },
  {
    key: "whatWorked",
    heading: "What worked?",
    hint: "Plays, runs, individual matchups",
    placeholder:
      "Full court press Q3\nBaseline drives broke zone\nTransition off steals",
    accent: "text-emerald-600",
  },
  {
    key: "whatDidnt",
    heading: "What didn't work?",
    hint: "Mistakes, breakdowns",
    placeholder:
      "Too many turnovers\nDidn't match intensity\n3pt shooting off",
    accent: "text-rose-600",
  },
  {
    key: "extra",
    heading: "Additional notes",
    hint: "",
    placeholder: "Other observations, key plays, adjustments…",
  },
];

export const EMPTY_SECTIONS: NoteSections = {
  whatTheyRan: "",
  oppTendencies: "",
  whatWorked: "",
  whatDidnt: "",
  extra: "",
};

/** Serialize 5 sections into a markdown blob with H2 headers. Empty sections
 * are omitted so notes stay tidy. */
export function sectionsToMarkdown(s: NoteSections): string {
  const out: string[] = [];
  for (const def of SECTION_DEFS) {
    const v = s[def.key].trim();
    if (v) out.push(`## ${def.heading}\n${v}`);
  }
  return out.join("\n\n");
}

/** Parse a markdown blob back into 5 sections by H2 heading. Unknown content
 * (no header, or pre-header text) lands in `extra`. */
export function markdownToSections(md: string): NoteSections {
  const sections: NoteSections = { ...EMPTY_SECTIONS };
  if (!md.trim()) return sections;

  const headingByText: Record<string, keyof NoteSections> = {};
  for (const def of SECTION_DEFS) {
    headingByText[def.heading.toLowerCase()] = def.key;
  }

  const lines = md.split("\n");
  let current: keyof NoteSections | "_pre" = "_pre";
  const buckets: Record<string, string[]> = { _pre: [] };
  for (const def of SECTION_DEFS) buckets[def.key] = [];

  for (const line of lines) {
    const m = line.match(/^##\s+(.+?)\s*$/);
    if (m) {
      const key = headingByText[m[1].toLowerCase()];
      current = key ?? "_pre";
      continue;
    }
    buckets[current].push(line);
  }

  for (const def of SECTION_DEFS) {
    sections[def.key] = (buckets[def.key] ?? []).join("\n").trim();
  }
  // Anything before the first heading goes into `extra` if extra is empty.
  const pre = (buckets._pre ?? []).join("\n").trim();
  if (pre && !sections.extra) sections.extra = pre;
  else if (pre) sections.extra = `${pre}\n\n${sections.extra}`;

  return sections;
}
