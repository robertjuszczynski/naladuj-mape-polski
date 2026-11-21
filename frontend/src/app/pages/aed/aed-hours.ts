const DAYS: Record<string, Record<string, string>> = {
  pl: { Mo: 'pn', Tu: 'wt', We: 'śr', Th: 'czw', Fr: 'pt', Sa: 'sob.', Su: 'nd', PH: 'święta' },
  en: { Mo: 'Mon', Tu: 'Tue', We: 'Wed', Th: 'Thu', Fr: 'Fri', Sa: 'Sat', Su: 'Sun', PH: 'holidays' },
};
const WORDS: Record<string, { always: string; daily: string; closed: string }> = {
  pl: { always: 'całodobowo', daily: 'codziennie', closed: 'nieczynne' },
  en: { always: '24/7', daily: 'daily', closed: 'closed' },
};
const RULE = /^(?:([A-Za-z,-]+)\s+)?(.+)$/;

/** Opening hours from the data standard ("Mo-Fr 08:00-16:00") in the page language ("pn–pt 8:00–16:00"). */
export function readableHours(spec: string | undefined, lang: string): string {
  const value = (spec ?? '').trim();
  const days = DAYS[lang] ?? DAYS['pl'];
  const words = WORDS[lang] ?? WORDS['pl'];
  if (value === '24/7') {
    return words.always;
  }
  const time = (t: string) => t.replace(/^0(\d)/, '$1');
  const rules = value.split(';').map((rule) => {
    const match = RULE.exec(rule.trim());
    if (!match) {
      return null;
    }
    const [, dayPart, ranges] = match;
    const dayText = dayPart && dayPart !== 'Mo-Su'
      ? dayPart
          .split(',')
          .map((part) =>
            part
              .split('-')
              .map((d) => days[d] ?? d)
              .join('–'),
          )
          .join(', ')
      : words.daily;
    const hours = /^(off|closed)$/.test(ranges)
      ? words.closed
      : ranges
          .split(',')
          .map((r) => r.split('-').map(time).join('–'))
          .join(', ');
    return `${dayText} ${hours}`;
  });
  return rules.every((r) => r) ? rules.join('; ') : value;
}
