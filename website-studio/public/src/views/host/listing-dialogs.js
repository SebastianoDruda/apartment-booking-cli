/** Host dialogs: publish a listing, reprice it, retire it (apartment add/update/remove). */
import { html } from '../../core/html.js';
import { t } from '../../core/i18n.js';
import { formatMoney, roundMoney } from '../../core/format.js';
import { MAX_GUESTS } from '../../config.js';
import { bookingService } from '../../services/booking-service.js';
import { stepper } from '../../ui/components.js';
import { confirmDialog, errorCopy, openDialog, toast, toastError } from '../../ui/feedback.js';
import { clearErrors, focusFirstInvalid, setFieldError, setLoading, showAlert, syncStepper } from '../../ui/forms.js';
import { icon } from '../../ui/icons.js';

function parsePrice(value) {
  const price = Number(String(value).replace(',', '.').replace('€', '').trim());
  return Number.isFinite(price) && roundMoney(price) > 0 ? roundMoney(price) : null;
}

export function openListingDialog() {
  return openDialog({
    title: t('host.listings.form.title'),
    description: t('host.listings.form.lead'),
    size: 'lg',
    content: html`<form class="form-grid" novalidate data-listing-form>
      <fieldset class="form-section field--full">
        <legend class="form-section__title">${t('host.listings.form.sections.place')}</legend>
        <div class="field">
          <label class="label" for="l-name">${t('host.listings.form.name')}</label>
          <input class="input" id="l-name" name="name" maxlength="80" autocomplete="off" placeholder="${t('host.listings.form.namePlaceholder')}" autofocus>
        </div>
      </fieldset>
      <fieldset class="form-section field--full">
        <legend class="form-section__title">${t('host.listings.form.sections.address')}</legend>
        <div class="field">
          <label class="label" for="l-street">${t('host.listings.form.street')}</label>
          <input class="input" id="l-street" name="street" autocomplete="address-line1">
        </div>
        <div class="field-row">
          <div class="field">
            <label class="label" for="l-city">${t('host.listings.form.city')}</label>
            <input class="input" id="l-city" name="city" autocomplete="address-level2">
          </div>
          <div class="field">
            <label class="label" for="l-country">${t('host.listings.form.country')}</label>
            <input class="input" id="l-country" name="country" autocomplete="country-name">
          </div>
        </div>
      </fieldset>
      <fieldset class="form-section field--full">
        <legend class="form-section__title">${t('host.listings.form.sections.stay')}</legend>
        <div class="field-row">
          <div class="field">
            <label class="label" for="l-price">${t('host.listings.form.price')}</label>
            <div class="input-affix"><span aria-hidden="true">€</span>
              <input class="input" id="l-price" name="price" type="number" inputmode="decimal" min="0.01" step="0.01" placeholder="120">
            </div>
          </div>
          <div class="field">
            <span class="label" id="l-capacity">${t('host.listings.form.capacity')}</span>
            ${stepper({ name: 'maxPeople', value: 2, min: 1, max: MAX_GUESTS, labelledby: 'l-capacity' })}
          </div>
        </div>
      </fieldset>
      <p class="form-alert field--full" role="alert" data-alert hidden></p>
      <div class="dialog__actions field--full">
        <button type="button" class="btn btn--ghost" data-close>${t('common.cancel')}</button>
        <button type="submit" class="btn btn--primary" data-submit>${icon('sparkles', 18)} ${t('host.listings.form.submit')}</button>
      </div>
    </form>`,
    onMount(dialog, close) {
      const form = dialog.querySelector('[data-listing-form]');
      const submit = form.querySelector('[data-submit]');
      const value = (name) => form.elements.namedItem(name).value;
      const read = () => ({
        name: value('name').trim(), country: value('country').trim(), city: value('city').trim(),
        street: value('street').trim(), maxPeople: Number(value('maxPeople')), price: parsePrice(value('price')),
      });
      form.addEventListener('input', (event) => {
        if (event.target.name) setFieldError(form, event.target.name, '');
      });
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearErrors(form);
        const data = read();
        const errors = {};
        ['name', 'country', 'city', 'street'].forEach((key) => { if (!data[key]) errors[key] = t('common.required'); });
        if (!Number.isInteger(data.maxPeople) || data.maxPeople < 1) errors.maxPeople = t('host.listings.errors.capacity');
        if (!data.price) errors.price = t('host.listings.errors.price');
        if (Object.keys(errors).length) {
          Object.entries(errors).forEach(([key, message]) => setFieldError(form, key, message));
          focusFirstInvalid(form);
          return;
        }
        setLoading(submit, true);
        try {
          close(await bookingService.addApartment(data));
        } catch (error) {
          setLoading(submit, false);
          if (error.code === 'conflict') {
            setFieldError(form, 'name', t('host.listings.errors.exists'));
            focusFirstInvalid(form);
          } else {
            showAlert(form.querySelector('[data-alert]'), errorCopy(error).message);
          }
        }
      });
      syncStepper(form.querySelector('[data-stepper]'));
    },
  }).then((apartment) => {
    if (apartment) toast({ title: t('host.listings.form.created', { name: apartment.name }), message: t('host.listings.form.createdLead') });
    return apartment;
  });
}

export function openPriceDialog(apartment) {
  return openDialog({
    title: t('host.listings.price.title', { name: apartment.name }),
    size: 'sm',
    content: html`<form class="stack" novalidate data-price-form>
      <div class="field">
        <label class="label" for="p-price">${t('host.listings.price.new')}</label>
        <div class="input-affix"><span aria-hidden="true">€</span>
          <input class="input" id="p-price" name="price" type="number" inputmode="decimal" min="0.01" step="0.01" value="${apartment.pricePerNight}" aria-describedby="p-price-hint" autofocus>
        </div>
        <p class="hint price-hint" id="p-price-hint">${t('host.listings.price.current')} ${formatMoney(apartment.pricePerNight)}<span class="delta" data-delta aria-live="polite"></span></p>
      </div>
      <p class="form-alert" role="alert" data-alert hidden></p>
      <div class="dialog__actions">
        <button type="button" class="btn btn--ghost" data-close>${t('common.cancel')}</button>
        <button type="submit" class="btn btn--primary" data-submit>${t('host.listings.price.submit')}</button>
      </div>
    </form>`,
    onMount(dialog, close) {
      const form = dialog.querySelector('[data-price-form]');
      const input = form.elements.namedItem('price');
      const delta = form.querySelector('[data-delta]');
      const submit = form.querySelector('[data-submit]');
      const update = () => {
        const price = parsePrice(input.value);
        const change = price ? Math.round(((price - apartment.pricePerNight) / apartment.pricePerNight) * 100) : 0;
        delta.textContent = price && change ? `${change > 0 ? '+' : '−'}${Math.abs(change)}%` : '';
        delta.className = `delta ${change > 0 ? 'delta--up-good' : change < 0 ? 'delta--down' : ''}`;
      };
      input.addEventListener('input', () => { setFieldError(form, 'price', ''); update(); });
      input.select();
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const price = parsePrice(input.value);
        if (!price) {
          setFieldError(form, 'price', t('host.listings.errors.price'));
          input.focus();
          return;
        }
        setLoading(submit, true);
        try {
          close(await bookingService.updatePrice(apartment.name, price));
        } catch (error) {
          setLoading(submit, false);
          showAlert(form.querySelector('[data-alert]'), errorCopy(error, { not_found: t('errors.listingGone') }).message);
        }
      });
      update();
    },
  }).then((updated) => {
    if (updated) {
      toast({ title: t('host.listings.price.updated'), message: `${updated.name}: ${formatMoney(updated.previousPrice)} → ${formatMoney(updated.pricePerNight)}` });
    }
    return updated;
  });
}

export async function removeListing(apartment, bookingCount) {
  const message = bookingCount
    ? `${t('host.listings.remove.body')} ${t('host.listings.remove.bodyBookings', { count: bookingCount })}`
    : t('host.listings.remove.body');
  const confirmed = await confirmDialog({
    title: t('host.listings.remove.title', { name: apartment.name }),
    message,
    confirmLabel: t('host.listings.remove.confirm'),
    requireText: bookingCount ? apartment.name : '',
  });
  if (!confirmed) return false;
  try {
    await bookingService.removeApartment(apartment.name);
    toast({ title: t('host.listings.remove.removed', { name: apartment.name }) });
    return true;
  } catch (error) {
    toastError(error, { not_found: t('errors.listingGone') });
    return true; // Refresh either way: the listing may already be gone.
  }
}
