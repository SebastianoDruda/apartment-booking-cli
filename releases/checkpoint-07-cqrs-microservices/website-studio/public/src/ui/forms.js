/** Form helpers: accessible inline errors, steppers and loading states. */

export function setFieldError(form, name, message) {
  const input = form.elements.namedItem(name);
  const field = input?.closest?.('.field');
  if (!field) return;
  let error = field.querySelector('.field__error');
  const hint = field.querySelector('.hint');

  if (!message) {
    input.removeAttribute('aria-invalid');
    error?.remove();
    if (hint?.id) input.setAttribute('aria-describedby', hint.id);
    else input.removeAttribute('aria-describedby');
    return;
  }
  if (!error) {
    error = document.createElement('p');
    error.className = 'field__error';
    error.id = `${input.id || name}-error`;
    field.append(error);
  }
  error.textContent = message;
  input.setAttribute('aria-invalid', 'true');
  input.setAttribute('aria-describedby', [hint?.id, error.id].filter(Boolean).join(' '));
}

export function clearErrors(form) {
  [...form.elements].forEach((element) => element.name && setFieldError(form, element.name, ''));
  form.querySelectorAll('[data-alert]').forEach((alert) => showAlert(alert, ''));
}

export function showAlert(element, message) {
  if (!element) return;
  element.textContent = message;
  element.hidden = !message;
}

export function setLoading(button, loading) {
  if (!button) return;
  button.classList.toggle('is-loading', loading);
  button.disabled = loading;
  button.setAttribute('aria-busy', String(loading));
}

/** Focus the first invalid control so keyboard and screen-reader users land on the problem. */
export function focusFirstInvalid(form) {
  form.querySelector('[aria-invalid="true"]')?.focus();
}

export function stepBy(button) {
  const root = button.closest('[data-stepper]');
  const input = root?.querySelector('input');
  if (!input || button.getAttribute('aria-disabled') === 'true') return;
  const min = Number(input.min || 1);
  const max = Number(input.max || 99);
  const current = Number.parseInt(input.value, 10);
  const base = Number.isFinite(current) ? current : min;
  input.value = String(Math.min(max, Math.max(min, base + Number(button.dataset.step))));
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

export function syncStepper(root) {
  const input = root.querySelector('input');
  if (!input) return;
  const value = Number(input.value);
  // aria-disabled (not disabled) keeps keyboard focus on the button at the bounds.
  root.querySelector('[data-step="-1"]')?.setAttribute('aria-disabled', String(value <= Number(input.min)));
  root.querySelector('[data-step="1"]')?.setAttribute('aria-disabled', String(value >= Number(input.max)));
}
