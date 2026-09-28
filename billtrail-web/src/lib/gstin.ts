const CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

/** Check character for the first 14 characters of a GSTIN (mod-36 algorithm). */
export function checkChar(first14: string): string {
  let sum = 0;
  for (let i = 0; i < 14; i++) {
    const v = CH.indexOf(first14[i]) * (i % 2 === 0 ? 1 : 2);
    sum += Math.floor(v / 36) + (v % 36);
  }
  return CH[(36 - (sum % 36)) % 36];
}

export function isValidGstin(input: string): boolean {
  const s = input.trim().toUpperCase();
  if (!/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(s)) return false;
  const state = Number(s.slice(0, 2));
  if (state < 1 || (state > 38 && state !== 97 && state !== 99)) return false;
  return checkChar(s.slice(0, 14)) === s[14];
}
