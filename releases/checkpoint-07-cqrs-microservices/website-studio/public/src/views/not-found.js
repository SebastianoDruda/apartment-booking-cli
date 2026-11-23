/** 404 view. */
import { html } from '../core/html.js';
import { t } from '../core/i18n.js';
import { miniFooter, publicHeader } from '../ui/chrome.js';
import { icon } from '../ui/icons.js';

export const notFoundView = {
  title: () => t('notFound.metaTitle'),
  render: (ctx) => html`
    <div class="page-frame">
    ${publicHeader(ctx)}
    <main id="main" class="not-found container" tabindex="-1">
      <p class="not-found__code display" aria-hidden="true">404</p>
      <h1 class="display">${t('notFound.title')}</h1>
      <p class="lead">${t('notFound.body')}</p>
      <a class="btn btn--primary btn--lg" href="#/">${icon('arrowLeft', 18)} ${t('notFound.cta')}</a>
    </main>
    ${miniFooter(ctx)}
    </div>`,
};
