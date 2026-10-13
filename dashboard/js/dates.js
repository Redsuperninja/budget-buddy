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

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// "2026-02" -> "Feb" (chart labels); January also shows its year: "Jan 2026".
export function monthLabel(month) {
  const [year, m] = month.split("-");
  return m === "01" ? `Jan ${year}` : MONTHS[Number(m) - 1];
}

const NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];

// "2026-09" -> "September", for sentences.
export const monthName = (month) => NAMES[Number(month.split("-")[1]) - 1];
