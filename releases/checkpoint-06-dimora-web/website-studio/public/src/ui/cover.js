/**
 * Generative apartment artwork. The API stores no photos, so every listing
 * gets a deterministic illustration whose palette and motif derive from its name.
 */
import { html, raw } from '../core/html.js';
import { hashString, initials } from '../core/format.js';

// Mediterranean / alpine hues: terracotta, ochre, sand, sage, lagoon, sea, dusk, rose.
const HUES = [14, 28, 40, 150, 172, 198, 222, 262, 342];

const ART = [
  // Arcade of arches under a sun
  raw(`<svg viewBox="0 0 200 125" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <circle cx="152" cy="36" r="17" fill="currentColor" opacity=".6"/>
    <path d="M0 125V86h200v39z" fill="currentColor" opacity=".16"/>
    <path d="M28 125V76a20 20 0 0 1 40 0v49zM80 125V64a24 24 0 0 1 48 0v61zM140 125V80a16 16 0 0 1 32 0v45z" fill="currentColor" opacity=".38"/>
  </svg>`),
  // Rolling hills
  raw(`<svg viewBox="0 0 200 125" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <circle cx="58" cy="42" r="19" fill="currentColor" opacity=".55"/>
    <path d="M0 125V86c30-18 62-22 98-8s68 10 102-6v53z" fill="currentColor" opacity=".28"/>
    <path d="M0 125v-20c40-15 82-15 122 0s58 9 78 0v20z" fill="currentColor" opacity=".45"/>
  </svg>`),
  // Facade with windows
  raw(`<svg viewBox="0 0 200 125" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <circle cx="40" cy="34" r="14" fill="currentColor" opacity=".5"/>
    <rect x="70" y="30" width="78" height="95" rx="4" fill="currentColor" opacity=".3"/>
    <g fill="currentColor" opacity=".6">
      <rect x="82" y="44" width="12" height="16" rx="6"/><rect x="103" y="44" width="12" height="16" rx="6"/><rect x="124" y="44" width="12" height="16" rx="6"/>
      <rect x="82" y="70" width="12" height="16" rx="2"/><rect x="103" y="70" width="12" height="16" rx="2"/><rect x="124" y="70" width="12" height="16" rx="2"/>
      <path d="M100 125v-18a9 9 0 0 1 18 0v18z"/>
    </g>
    <path d="M0 125v-10h200v10z" fill="currentColor" opacity=".25"/>
  </svg>`),
  // Lake and mountains
  raw(`<svg viewBox="0 0 200 125" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <circle cx="150" cy="30" r="13" fill="currentColor" opacity=".55"/>
    <path d="m0 98 46-52 30 30 34-44 52 66H0z" fill="currentColor" opacity=".32"/>
    <path d="M0 98h200v27H0z" fill="currentColor" opacity=".18"/>
    <path d="M24 108h40M110 112h56M70 118h30" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".5"/>
  </svg>`),
];

export function coverIdentity(name = '') {
  const hash = hashString(name);
  return { hue: HUES[hash % HUES.length], variant: (hash >>> 5) % ART.length };
}

export function cover(item, { size = 'md', monogram = true, hue: fixedHue, variant: fixedVariant } = {}) {
  const identity = coverIdentity(item.name);
  const hue = fixedHue ?? identity.hue;
  const variant = fixedVariant ?? identity.variant;
  return html`<div class="cover cover--${size}" data-hue="${hue}" aria-hidden="true">${ART[variant]}${
    monogram ? html`<span class="cover__mono">${initials(item.name)}</span>` : ''
  }</div>`;
}
