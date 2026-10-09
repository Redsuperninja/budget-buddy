// Light, dark, or follow the computer's setting (the default). The choice is kept in this browser
// (or app window) only; app.css picks the colors with light-dark() and the data-theme attribute.

import { savedChoice } from "./prefs.js";

export const THEMES = [["system", "Match my computer"], ["light", "Light"], ["dark", "Dark"]];

const theme = savedChoice("budget-buddy-theme", THEMES, "data-theme");

// Anything that isn't a known choice means "system", which removes data-theme so the computer decides.
export const parseTheme = theme.parse;
export const loadTheme = theme.load;
export const saveTheme = theme.save;
export const applyTheme = theme.apply;
