// Money is whole cents everywhere. These turn cents into dollars and typed dollars into cents,
// using string logic only (no floating-point maths on money).

export function formatCents(cents) {
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100).toLocaleString("en-US");
  return `${cents < 0 ? "-" : ""}$${dollars}.${String(abs % 100).padStart(2, "0")}`;
}

// Cards and loans: a negative balance is money you owe.
export function formatBalance(cents, kind) {
  if ((kind === "credit_card" || kind === "loan") && cents < 0) return `${formatCents(-cents)} owed`;
  return formatCents(cents);
}

// For text boxes: 25000 -> "250.00".
export function centsToInput(cents) {
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;
}

// "12", "12.5", ".50", "12.", "$1,234.56", "-5" -> integer cents, or null if it isn't an amount.
export function parseDollars(text) {
  let t = String(text).trim().replace(/[$,\s]/g, "");
  const negative = t.startsWith("-");
  if (negative) t = t.slice(1);
  if (!/^(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const [whole, fraction = ""] = t.split(".");
  if (fraction.length > 2 || whole.length > 12) return null;
  const cents = Number(whole || "0") * 100 + Number((fraction + "00").slice(0, 2));
  return negative ? -cents : cents;
}

// parseDollars for form handlers: a plain-English error instead of null.
export function centsOrThrow(text, what = "amount") {
  const cents = parseDollars(text);
  if (cents === null) throw new Error(`Please enter the ${what} as a number, like 12.50.`);
  return cents;
}
