/**
 * Token and character-level difference algorithm for visual audit comparison.
 */

export interface DiffToken {
  type: 'added' | 'removed' | 'unchanged';
  value: string;
}

export function computeTokenDiff(oldText: string, newText: string): DiffToken[] {
  if (oldText === newText) {
    return [{ type: 'unchanged', value: newText }];
  }

  const oldTokens = oldText.split(/(\s+|[.,;()\-:])/);
  const newTokens = newText.split(/(\s+|[.,;()\-:])/);

  const result: DiffToken[] = [];
  let i = 0;
  let j = 0;

  while (i < oldTokens.length && j < newTokens.length) {
    if (oldTokens[i] === newTokens[j]) {
      result.push({ type: 'unchanged', value: oldTokens[i] });
      i++;
      j++;
    } else {
      // Lookahead check for insertion or deletion
      const findInNew = newTokens.indexOf(oldTokens[i], j);
      const findInOld = oldTokens.indexOf(newTokens[j], i);

      if (findInNew !== -1 && (findInOld === -1 || findInNew - j <= findInOld - i)) {
        while (j < findInNew) {
          result.push({ type: 'added', value: newTokens[j] });
          j++;
        }
      } else if (findInOld !== -1) {
        while (i < findInOld) {
          result.push({ type: 'removed', value: oldTokens[i] });
          i++;
        }
      } else {
        result.push({ type: 'removed', value: oldTokens[i] });
        result.push({ type: 'added', value: newTokens[j] });
        i++;
        j++;
      }
    }
  }

  while (i < oldTokens.length) {
    result.push({ type: 'removed', value: oldTokens[i] });
    i++;
  }

  while (j < newTokens.length) {
    result.push({ type: 'added', value: newTokens[j] });
    j++;
  }

  return result;
}
