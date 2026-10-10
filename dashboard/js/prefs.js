// A choice from a short list that this browser (or app window) remembers, like Colors or View, shown as an
// attribute on <html> for app.css to read. Never throws, even when the browser blocks storage.

// choices: [[value, label], ...]; the first is the default, which removes the attribute.
export function savedChoice(key, choices, attribute) {
  const fallback = choices[0][0];
  const parse = (text) => (choices.some(([value]) => value === text) ? text : fallback);
  return {
    parse,
    // storage: window.localStorage, or null when the browser blocks it.
    load(storage) {
      try {
        return parse(storage ? storage.getItem(key) : null);
      } catch {
        return fallback;
      }
    },
    save(storage, choice) {
      try {
        if (storage) storage.setItem(key, parse(choice));
      } catch {
        /* private mode or storage turned off: the choice lasts until the page closes */
      }
    },
    apply(root, choice) {
      const value = parse(choice);
      if (value === fallback) root.removeAttribute(attribute);
      else root.setAttribute(attribute, value);
    },
  };
}
