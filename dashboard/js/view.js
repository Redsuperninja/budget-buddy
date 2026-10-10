// Simple view (the default) or All tools. Simple hides the power-user pages and controls, which are marked
// with the "advanced" class (app.css hides them unless <html> has data-view="all"). Kept in this browser only.

import { savedChoice } from "./prefs.js";

export const VIEWS = [["simple", "Simple"], ["all", "All tools"]];

const view = savedChoice("budget-buddy-view", VIEWS, "data-view");

export const parseView = view.parse;
export const loadView = view.load;
export const saveView = view.save;
export const applyView = view.apply;
