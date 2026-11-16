/**
 * Route table. `access` drives the guard in main.js:
 *   public    — anyone
 *   anonymous — signed-out users only (signed-in users go to their home)
 *   guest     — signed-in guests (people who book)
 *   host      — signed-in hosts (people who list apartments)
 */
import { landingView } from './views/landing.js';
import { authView } from './views/auth.js';
import { exploreView } from './views/guest/explore.js';
import { bookingsView, tripsView } from './views/guest/trips.js';
import { overviewView } from './views/host/overview.js';
import { listingsView } from './views/host/listings.js';
import { reservationsView } from './views/host/reservations.js';
import { notFoundView } from './views/not-found.js';

export const routes = [
  { path: '/', view: landingView, access: 'public' },
  { path: '/login', view: authView, access: 'anonymous' },
  { path: '/guest/explore', view: exploreView, access: 'guest', layout: 'app' },
  { path: '/guest/trips', view: tripsView, access: 'guest', layout: 'app' },
  { path: '/guest/bookings', view: bookingsView, access: 'guest', layout: 'app' },
  { path: '/host/overview', view: overviewView, access: 'host', layout: 'app' },
  { path: '/host/listings', view: listingsView, access: 'host', layout: 'app' },
  { path: '/host/reservations', view: reservationsView, access: 'host', layout: 'app' },
];

export const notFoundRoute = { path: '*', view: notFoundView, access: 'public' };
