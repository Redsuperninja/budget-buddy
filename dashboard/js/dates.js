// Dates as the Home Base wants them: "YYYY-MM-DD" days and "YYYY-MM" months, in local time.

const pad = (n) => String(n).padStart(2, "0");

export const thisYear = () => new Date().getFullYear();

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

export function today() {
  return `${currentMonth()}-${pad(new Date().getDate())}`;
}

// "2026-02" -> { from: "2026-02-01", to: "2026-02-28" }
export function monthRange(month) {
  const [year, m] = month.split("-").map(Number);
  return { from: `${month}-01`, to: `${month}-${pad(new Date(year, m, 0).getDate())}` };
}
