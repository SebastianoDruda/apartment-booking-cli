/**
 * Domain gateway: maps the REST API (snake_case) to view models (camelCase).
 * Business rules — capacity, overlaps, pricing — stay in the Python engine;
 * the client only mirrors them for instant feedback.
 */
import { api as defaultApi } from './api.js';

export function splitAddress(address = '') {
  const [country = '', city = '', ...street] = address.split(',');
  return { country: country.trim(), city: city.trim(), street: street.join(',').trim() };
}

export function toApartment(raw) {
  return {
    id: raw.id,
    name: raw.name,
    address: raw.address,
    ...splitAddress(raw.address),
    maxPeople: raw.max_people,
    pricePerNight: raw.price_per_night,
    nights: raw.nights ?? null,
    total: raw.total_price ?? null,
    start: raw.start_date ?? null,
    end: raw.end_date ?? null,
  };
}

export function toBooking(raw) {
  return {
    id: raw.id,
    apartmentId: raw.apartment_id,
    apartmentName: raw.apartment_name,
    address: raw.apartment_address,
    ...splitAddress(raw.apartment_address),
    maxPeople: raw.apartment_max_people,
    pricePerNight: raw.price_per_night,
    guestName: raw.booker_name,
    start: raw.start_date,
    end: raw.end_date,
    nights: raw.nights,
    people: raw.num_people,
    total: raw.total_price,
  };
}

export function createBookingService(api = defaultApi) {
  const apartmentPath = (name) => `/apartments/${encodeURIComponent(name)}`;

  return {
    async listApartments(options) {
      return (await api.get('/apartments', options)).map(toApartment);
    },

    async searchAvailability({ start, end, guests }, options) {
      const query = { start_date: start, end_date: end, num_people: String(guests) };
      return (await api.get('/availability', { ...options, query })).map(toApartment);
    },

    async addApartment({ name, country, city, street, maxPeople, price }) {
      return toApartment(await api.post('/apartments', {
        name, country, city, street_and_number: street, max_people: maxPeople, price_per_night: price,
      }));
    },

    async updatePrice(name, price) {
      const result = await api.patch(`${apartmentPath(name)}/price`, { price_per_night: price });
      return { ...toApartment(result), previousPrice: result.old_price_per_night };
    },

    async removeApartment(name) {
      return toApartment(await api.delete(apartmentPath(name)));
    },

    async listBookings(options) {
      return (await api.get('/bookings', options)).map(toBooking);
    },

    async createBooking({ apartmentName, start, end, guestName, guests }) {
      return toBooking(await api.post('/bookings', {
        apartment_name: apartmentName, start_date: start, end_date: end,
        booker_name: guestName, num_people: guests,
      }));
    },

    async changeBooking({ apartmentName, start, end, newStart, newEnd, guests }) {
      return toBooking(await api.patch('/bookings', {
        apartment_name: apartmentName, start_date: start, end_date: end,
        new_start_date: newStart, new_end_date: newEnd, num_people: guests,
      }));
    },

    async cancelBooking({ apartmentName, start, end }) {
      return api.delete('/bookings', {
        body: { apartment_name: apartmentName, start_date: start, end_date: end },
      });
    },
  };
}

export const bookingService = createBookingService();
