const ROMAN_REGEX =
  /^(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx|xxi|xxii|xxiii|xxiv|xxv|xxvi|xxvii|xxviii|xxix|xxx)$/i;

function romanToInt(s: string): number | null {
  const clean = s.toLowerCase();
  if (!ROMAN_REGEX.test(clean)) return null;
  const map: Record<string, number> = {
    i: 1,
    v: 5,
    x: 10,
    l: 50,
    c: 100,
    d: 500,
    m: 1000,
  };
  let total = 0;
  let prev = 0;
  for (let i = clean.length - 1; i >= 0; i--) {
    const curr = map[clean[i]];
    if (curr >= prev) total += curr;
    else total -= curr;
    prev = curr;
  }
  return total;
}

export function parseSegment(seg: string): [string, number, number, string] {
  if (!seg.includes('_')) {
    return [seg, 0, 0, ''];
  }
  const idx = seg.indexOf('_');
  const prefix = seg.substring(0, idx);
  const rest = seg.substring(idx + 1);

  // 1. Numeric check (e.g. c_1, c_2, c_10, a_5)
  if (/^\d+$/.test(rest)) {
    return [prefix, 0, parseInt(rest, 10), ''];
  }

  // 2. Roman numeral check (e.g. c_i, c_ii, c_ix, c_x)
  const romanVal = romanToInt(rest);
  if (romanVal !== null) {
    return [prefix, 0, romanVal, ''];
  }

  // 3. Alphabetic check (e.g. p_a, p_b, p_dd)
  return [prefix, 1, 0, rest.toLowerCase()];
}

export function naturalPathCompare(pathA: string, pathB: string): number {
  if (!pathA) return -1;
  if (!pathB) return 1;

  const partsA = pathA.split('.');
  const partsB = pathB.split('.');
  const minLen = Math.min(partsA.length, partsB.length);

  for (let i = 0; i < minLen; i++) {
    const [prefA, typeA, numA, strA] = parseSegment(partsA[i]);
    const [prefB, typeB, numB, strB] = parseSegment(partsB[i]);

    if (prefA !== prefB) {
      const cmpPref = prefA.localeCompare(prefB);
      if (cmpPref !== 0) return cmpPref;
    }
    if (typeA !== typeB) {
      return typeA - typeB;
    }
    if (numA !== numB) {
      return numA - numB;
    }
    if (strA !== strB) {
      const cmpStr = strA.localeCompare(strB, 'vi', { sensitivity: 'base' });
      if (cmpStr !== 0) return cmpStr;
    }
  }

  return partsA.length - partsB.length;
}
