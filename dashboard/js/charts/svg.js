// Building SVG charts the same safe way as dom.js: elements and text nodes only, never markup.

import { append } from "../dom.js";

const SVG_NS = "http://www.w3.org/2000/svg"; // a fixed name, never fetched

export function s(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, String(value));
  }
  append(el, children);
  return el;
}
