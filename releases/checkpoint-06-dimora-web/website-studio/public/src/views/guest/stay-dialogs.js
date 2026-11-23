/** Booking and change-of-plans dialogs with live price feedback. */
import { html, render } from '../../core/html.js';
import { t } from '../../core/i18n.js';
import { addDays, formatMoney, nightsBetween, roundMoney, todayIso } from '../../core/format.js';
import { bookingService } from '../../services/booking-service.js';
import { place, stepper } from '../../ui/components.js';
import { cover } from '../../ui/cover.js';
import { errorCopy, openDialog } from '../../ui/feedback.js';
import { setLoading, showAlert, syncStepper } from '../../ui/forms.js';
import { icon } from '../../ui/icons.js';

function stayForm({ apartment, start = '', end = '', guests = 1, minDate = '', submitLabel }) {
  return html`<form class="stay-form" novalidate data-stay-form>
    <div class="stay-form__head">
      ${cover(apartment, { size: 'sm' })}
      <div><strong>${apartment.name}</strong><span class="muted">${icon('pin', 14)} ${place(apartment)}</span></div>
    </div>
    <div class="field-row">
      <div class="field">
        <label class="label" for="stay-start">${t('explore.checkIn')}</label>
        <input class="input" id="stay-start" type="date" name="start" value="${start}" ${minDate ? html`min="${minDate}"` : ''} required>
      </div>
      <div class="field">
        <label class="label" for="stay-end">${t('explore.checkOut')}</label>
        <input class="input" id="stay-end" type="date" name="end" value="${end}" min="${start ? addDays(start, 1) : minDate ? addDays(minDate, 1) : ''}" required>
      </div>
    </div>
    <div class="field">
      <span class="label" id="stay-guests-label">${t('explore.guests')}</span>
      <div class="field__inline">
        ${stepper({ name: 'guests', value: guests, min: 1, max: apartment.maxPeople, labelledby: 'stay-guests-label' })}
        <span class="hint">${t('booking.maxGuests', { count: apartment.maxPeople })}</span>
      </div>
    </div>
    <div class="price-summary" data-summary aria-live="polite"></div>
    <p class="form-alert" role="alert" data-alert hidden></p>
    <div class="dialog__actions">
      <button type="button" class="btn btn--ghost" data-close>${t('common.cancel')}</button>
      <button type="submit" class="btn btn--primary" data-submit>${submitLabel}</button>
    </div>
  </form>`;
}

function summary(apartment, { start, end }, previous) {
  const nights = start && end && end > start ? nightsBetween(start, end) : 0;
  if (!nights) {
    return html`<p class="price-summary__empty">${icon('calendar', 16)} ${t('booking.selectDates')}</p>`;
  }
  const total = roundMoney(nights * apartment.pricePerNight);
  const delta = previous ? roundMoney(total - previous.total) : 0;
  return html`
    <div class="price-summary__row"><span>${t('booking.breakdown', {
      price: formatMoney(apartment.pricePerNight), nights: t('common.nights', { count: nights }),
    })}</span><span>${formatMoney(total)}</span></div>
    ${previous ? html`<div class="price-summary__row muted"><span>${t('trips.before')}</span><span>${formatMoney(previous.total)}</span></div>
      <div class="price-summary__row"><span>${t('trips.difference')}</span>
        <span class="delta ${delta > 0 ? 'delta--up' : delta < 0 ? 'delta--down' : ''}">${delta > 0 ? '+' : delta < 0 ? '−' : '±'}${formatMoney(Math.abs(delta))}</span></div>` : ''}
    <div class="price-summary__row price-summary__row--total"><span>${t('common.total')}</span><strong>${formatMoney(total)}</strong></div>`;
}

function validate({ start, end, guests }, { minDate, maxPeople }) {
  if (!start || !end) return { field: start ? 'end' : 'start', message: t('booking.errors.dates') };
  if (minDate && start < minDate) return { field: 'start', message: t('booking.errors.pastDate') };
  if (end <= start) return { field: 'end', message: t('booking.errors.endAfterStart') };
  if (!Number.isInteger(guests) || guests < 1) return { field: 'guests', message: t('booking.errors.min') };
  if (guests > maxPeople) return { field: 'guests', message: t('booking.errors.capacity', { count: maxPeople }) };
  return null;
}

function wireStayForm(dialog, close, { apartment, minDate, previous, submit, overrides }) {
  const form = dialog.querySelector('[data-stay-form]');
  const summaryEl = form.querySelector('[data-summary]');
  const alert = form.querySelector('[data-alert]');
  const button = form.querySelector('[data-submit]');
  const field = (name) => form.elements.namedItem(name);
  const read = () => ({ start: field('start').value, end: field('end').value, guests: Number(field('guests').value) });

  const update = () => {
    const values = read();
    field('end').min = values.start ? addDays(values.start, 1) : '';
    render(summaryEl, summary(apartment, values, previous));
  };

  form.addEventListener('input', () => { showAlert(alert, ''); update(); });
  form.addEventListener('change', (event) => {
    if (event.target.name === 'start' && field('end').value && field('end').value <= field('start').value) {
      field('end').value = '';
    }
    update();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = read();
    const problem = validate(values, { minDate, maxPeople: apartment.maxPeople });
    if (problem) {
      showAlert(alert, problem.message);
      field(problem.field)?.focus();
      return;
    }
    setLoading(button, true);
    try {
      close(await submit(values));
    } catch (error) {
      setLoading(button, false);
      showAlert(alert, errorCopy(error, overrides).message);
    }
  });

  syncStepper(form.querySelector('[data-stepper]'));
  update();
  (field('start').value ? button : field('start')).focus();
}

export function openBookingDialog({ apartment, criteria = {}, session }) {
  const minDate = todayIso();
  return openDialog({
    title: t('explore.bookTitle', { name: apartment.name }),
    content: stayForm({
      apartment,
      start: criteria.start ?? '',
      end: criteria.end ?? '',
      guests: Math.min(Math.max(criteria.guests || 1, 1), apartment.maxPeople),
      minDate,
      submitLabel: t('explore.confirm'),
    }),
    onMount: (dialog, close) => wireStayForm(dialog, close, {
      apartment,
      minDate,
      overrides: { conflict: t('errors.bookingConflict'), not_found: t('errors.listingGone') },
      submit: (values) => bookingService.createBooking({
        apartmentName: apartment.name, start: values.start, end: values.end,
        guestName: session.name, guests: values.guests,
      }),
    }),
  });
}

export function openChangeDialog(booking) {
  const apartment = {
    name: booking.apartmentName, city: booking.city, country: booking.country, address: booking.address,
    maxPeople: booking.maxPeople, pricePerNight: booking.pricePerNight,
  };
  return openDialog({
    title: t('trips.changeTitle'),
    description: t('trips.changeLead'),
    content: stayForm({
      apartment, start: booking.start, end: booking.end, guests: booking.people, submitLabel: t('trips.changeSave'),
    }),
    onMount: (dialog, close) => wireStayForm(dialog, close, {
      apartment,
      previous: booking,
      overrides: { conflict: t('errors.bookingConflict'), not_found: t('errors.bookingGone') },
      submit: (values) => bookingService.changeBooking({
        apartmentName: booking.apartmentName, start: booking.start, end: booking.end,
        newStart: values.start, newEnd: values.end, guests: values.guests,
      }),
    }),
  });
}
