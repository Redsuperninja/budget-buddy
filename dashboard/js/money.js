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

// For chart axes, in whole dollars: 95000 -> "$950", 123456 -> "$1.2k", 250000000 -> "$2.5M".
export function shortDollars(cents) {
  const sign = cents < 0 ? "-" : "";
  const dollars = Math.round(Math.abs(cents) / 100);
  if (dollars < 1000) return `${sign}$${dollars}`;
  const [value, unit] = dollars < 1e6 ? [dollars / 1e3, "k"] : [dollars / 1e6, "M"];
  return `${sign}$${Number(value.toFixed(1))}${unit}`;
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

// A balance typed as the bank shows it, to cents. Cards and loans are typed as what you owe (a minus sign
// if the card owes you), stored as negative when owed. Throws a plain-English error if it isn't an amount.
export function bankBalanceToCents(text, kind) {
  const cents = centsOrThrow(text, "balance");
  return (kind === "credit_card" || kind === "loan") ? -cents || 0 : cents;
}

// parseDollars for form handlers: a plain-English error instead of null.
export function centsOrThrow(text, what = "amount") {
  const cents = parseDollars(text);
  if (cents === null) throw new Error(`Please enter the ${what} as a number, like 12.50.`);
  return cents;
}

// Money in and money out of a list of signed amounts in cents: { in, out }, both positive.
export function inAndOut(amounts) {
  return amounts.reduce((t, a) => (a > 0 ? { ...t, in: t.in + a } : { ...t, out: t.out - a }), { in: 0, out: 0 });
}
