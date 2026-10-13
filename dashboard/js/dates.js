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

// Whole days from "YYYY-MM-DD..." (a date, or the date part of a date and time) to `today` ("YYYY-MM-DD").
export function daysBetween(from, today) {
  const day = (text) => Date.UTC(...text.slice(0, 10).split("-").map((n, i) => Number(n) - (i === 1 ? 1 : 0)));
  return Math.round((day(today) - day(from)) / 86_400_000);
}

// "today", "yesterday" or "12 days ago".
export function agoText(days) {
  if (days <= 0) return "today";
  return days === 1 ? "yesterday" : `${days} days ago`;
}

// The local "YYYY-MM-DD" of a time the Home Base saved in UTC without saying so ("2026-10-13T02:30:00").
// offsetMinutes: this computer's offset from UTC as getTimezoneOffset() gives it (minutes behind UTC).
export function localDate(utcText, offsetMinutes = new Date(`${utcText}Z`).getTimezoneOffset()) {
  return new Date(Date.parse(`${utcText}Z`) - offsetMinutes * 60_000).toISOString().slice(0, 10);
}
