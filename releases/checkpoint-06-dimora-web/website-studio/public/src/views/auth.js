/**
 * Entry: one line and the role's mark on the left, two doors on the right.
 * The host door opens the host's space; the guest door first asks the guest's name,
 * used as the booker name like the CLI's "Your name". Pointing at a door previews it.
 */
import { html } from '../core/html.js';
import { t, tRich } from '../core/i18n.js';
import { MAX_NAME_LENGTH, ROLES } from '../config.js';
import { auth } from '../services/auth.js';
import { miniFooter } from '../ui/chrome.js';
import { brand, themeToggle } from '../ui/components.js';
import { showAlert } from '../ui/forms.js';
import { icon, roleMark } from '../ui/icons.js';

const ROLE_ICONS = { guest: 'suitcase', host: 'key' };

function visual(role) {
  return html`<div class="auth__mark">${roleMark(role, 64)}<span class="auth__mark-name">Dimora <b>${t(`roles.${role}`)}</b></span></div>
    <p class="display auth__visual-title">${tRich(`auth.${role}.visualTitle`)}</p>`;
}

export const authView = {
  title: () => t('auth.metaTitle'),

  render(ctx) {
    const role = ROLES.includes(ctx.query.role) ? ctx.query.role : 'guest';
    return html`<div class="auth" data-role="${role}">
      <aside class="auth__visual" aria-hidden="true">
        <div class="aurora aurora--auth"><span></span><span></span><span></span></div>
        <div class="grain"></div>
        <div class="auth__visual-copy" data-visual>${visual(role)}</div>
      </aside>

      <main id="main" class="auth__main" tabindex="-1">
        <div class="auth__top">
          <a class="link-back" href="#/">${icon('arrowLeft', 18)} ${t('auth.back')}</a>
          ${themeToggle()}
        </div>
        <div class="auth__panel">
          <div class="auth__mobile-brand">${brand()}</div>
          <h1 class="display auth__title" data-title>${t('auth.title')}</h1>
          <div class="doors" data-doors>
            ${ROLES.map((item) => html`<button type="button" class="door door--${item}" data-enter="${item}"
              ${item === role ? html`data-preferred` : ''}>
              <span class="door__icon">${icon(ROLE_ICONS[item], 22)}</span>
              <span class="door__text"><strong>${t(`auth.${item}.enter`)}</strong><span>${t(`auth.${item}.body`)}</span></span>
              <span class="door__arrow">${icon('arrowRight', 20)}</span>
            </button>`)}
          </div>
          <form class="stack name-step" data-name-step novalidate hidden>
            <div class="field">
              <label class="label" for="guest-name">${t('auth.guest.nameLabel')}</label>
              <input class="input" id="guest-name" name="name" maxlength="${MAX_NAME_LENGTH}" autocomplete="name"
                value="${auth.lastGuestName()}" aria-describedby="guest-name-hint">
              <span class="hint" id="guest-name-hint">${t('auth.guest.nameHint')}</span>
            </div>
            <p class="form-alert" role="alert" data-alert hidden></p>
            <div class="dialog__actions">
              <button type="button" class="btn btn--ghost" data-back>${t('auth.otherRole')}</button>
              <button type="submit" class="btn btn--primary">${t('auth.continue')} ${icon('arrowRight', 18)}</button>
            </div>
          </form>
        </div>
        ${miniFooter(ctx)}
      </main>
    </div>`;
  },

  mount(root, ctx) {
    const shell = root.querySelector('.auth');
    const slot = root.querySelector('[data-visual]');
    let shown = shell.dataset.role;

    const preview = (role) => {
      if (role === shown) return;
      shown = role;
      shell.dataset.role = role;
      slot.innerHTML = visual(role).value;
    };

    const doors = root.querySelector('[data-doors]');
    const title = root.querySelector('[data-title]');
    const nameStep = root.querySelector('[data-name-step]');
    const nameInput = nameStep.elements.namedItem('name');
    const alert = nameStep.querySelector('[data-alert]');

    const askName = (open) => {
      doors.hidden = open;
      nameStep.hidden = !open;
      title.textContent = t(open ? 'auth.guest.nameTitle' : 'auth.title');
      showAlert(alert, '');
      if (open) {
        preview('guest');
        nameInput.focus();
        nameInput.select();
      } else {
        doors.querySelector('[data-enter="guest"]').focus();
      }
    };

    const doorOf = (event) => event.target.closest('[data-enter]');
    doors.addEventListener('pointerover', (event) => { const door = doorOf(event); if (door) preview(door.dataset.enter); });
    doors.addEventListener('focusin', (event) => { const door = doorOf(event); if (door) preview(door.dataset.enter); });
    doors.addEventListener('click', (event) => {
      const door = doorOf(event);
      if (!door) return;
      if (door.dataset.enter === 'guest') askName(true);
      else ctx.app.signedIn(auth.enter(door.dataset.enter));
    });

    nameStep.querySelector('[data-back]').addEventListener('click', () => askName(false));
    nameInput.addEventListener('input', () => showAlert(alert, ''));
    nameStep.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!nameInput.value.trim()) {
        showAlert(alert, t('auth.guest.nameRequired'));
        nameInput.setAttribute('aria-invalid', 'true');
        nameInput.focus();
        return;
      }
      ctx.app.signedIn(auth.enter('guest', nameInput.value));
    });
  },
};
