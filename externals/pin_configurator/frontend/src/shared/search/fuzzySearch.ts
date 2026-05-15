export function normalizeFuzzyText(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function scoreFuzzyMatch(haystack: string, query: string): number | null {
  const normalizedHaystack = normalizeFuzzyText(haystack);
  const normalizedQuery = normalizeFuzzyText(query);

  if (!normalizedQuery) {
    return 0;
  }

  if (!normalizedHaystack) {
    return null;
  }

  const directIndex = normalizedHaystack.indexOf(normalizedQuery);
  if (directIndex >= 0) {
    return 10_000 - directIndex * 16 - Math.max(normalizedHaystack.length - normalizedQuery.length, 0);
  }

  let haystackIndex = 0;
  let matchedCharacters = 0;
  let score = 0;
  let streak = 0;
  let tokenStarts = 0;

  for (let queryIndex = 0; queryIndex < normalizedQuery.length; queryIndex += 1) {
    const queryCharacter = normalizedQuery[queryIndex];
    if (queryCharacter === " ") {
      streak = 0;
      continue;
    }

    let foundAt = -1;
    while (haystackIndex < normalizedHaystack.length) {
      if (normalizedHaystack[haystackIndex] === queryCharacter) {
        foundAt = haystackIndex;
        haystackIndex += 1;
        break;
      }
      haystackIndex += 1;
    }

    if (foundAt < 0) {
      return null;
    }

    matchedCharacters += 1;
    const previousCharacter = normalizedHaystack[foundAt - 1] ?? "";
    const startsToken = foundAt === 0 || previousCharacter === " ";
    if (startsToken) {
      tokenStarts += 1;
    }

    streak = foundAt > 0 && normalizedHaystack[foundAt - 1] === normalizedQuery[queryIndex - 1] ? streak + 1 : 1;
    score += 24 + streak * 18 + (startsToken ? 40 : 0);
  }

  if (!matchedCharacters) {
    return null;
  }

  return score + tokenStarts * 30 - Math.max(normalizedHaystack.length - matchedCharacters, 0);
}

export function filterAndRankByFuzzyMatch<T>(items: readonly T[], query: string, getSearchableText: (item: T) => string): T[] {
  const normalizedQuery = normalizeFuzzyText(query);
  if (!normalizedQuery) {
    return [...items];
  }

  return items
    .map((item, index) => ({
      item,
      index,
      score: scoreFuzzyMatch(getSearchableText(item), normalizedQuery),
    }))
    .filter((entry): entry is { item: T; index: number; score: number } => entry.score !== null)
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map((entry) => entry.item);
}