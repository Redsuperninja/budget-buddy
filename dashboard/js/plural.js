// "1 paycheck", "5 paychecks": a count with its noun, so screens never write "paycheck(s)".
// The noun is the singular; a regular plural just adds "s". Pass the plural for the odd ones.
// "1 sale may be a wash sale" / "3 sales may be wash sales".
export const washSales = (count) =>
  count === 1 ? "1 sale may be a wash sale." : `${count} sales may be wash sales.`;

export const plural = (count, singular, pluralForm = `${singular}s`) =>
  `${count} ${count === 1 ? singular : pluralForm}`;
