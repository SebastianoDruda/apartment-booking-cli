/**
 * Safe HTML templating.
 *
 * Every interpolated value is HTML-escaped unless it is itself a SafeHtml
 * produced by `html` or explicitly marked with `raw`. Views therefore cannot
 * inject markup by accident, even when rendering user- or API-provided text.
 */

export class SafeHtml {
  constructor(value) {
    this.value = value;
  }

  toString() {
    return this.value;
  }
}

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '`': '&#96;' };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"'`]/g, (char) => ESCAPES[char]);
}

function toMarkup(value) {
  if (value === null || value === undefined || value === false) return '';
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(toMarkup).join('');
  return escapeHtml(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, index) => {
    out += toMarkup(value) + strings[index + 1];
  });
  return new SafeHtml(out);
}

/** Mark trusted, static markup (icons, SVG art) as safe. Never pass user input. */
export function raw(markup) {
  return new SafeHtml(String(markup));
}

/**
 * Replace the children of `target` and apply CSS custom properties declared as
 * data attributes. Styles are set through the CSSOM so the strict CSP
 * (no inline style attributes) stays intact.
 */
export function render(target, content) {
  target.innerHTML = toMarkup(content);
  applyStyleHooks(target);
}

export function applyStyleHooks(root) {
  root.querySelectorAll('[data-hue]').forEach((node) => node.style.setProperty('--hue', node.dataset.hue));
  root.querySelectorAll('[data-meter]').forEach((node) => node.style.setProperty('--target', node.dataset.meter));
}
