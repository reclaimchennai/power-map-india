// Fuel identity for every view (map pillars, chips, mix bar, cards). Colours are the reference categorical
// slots in their dark and light steps, each validated as a stacked set on its panel surface in the order
// coal · wind · gas · hydro · solar · nuclear · bio (CVD in the 6-8 warn band; three light steps are under
// 3:1), so identity is never colour alone: every fuel has its own pixel icon and a text label.
export const FUELS = {
  coal:           { label: 'Coal',            dark: '#e66767', light: '#e34948', icon: 'coal',           group: 'coal',    smoke: 0xb9bcc2, thermal: true },
  lignite:        { label: 'Lignite',         dark: '#e66767', light: '#e34948', icon: 'lignite',        group: 'coal',    smoke: 0xa89e92, thermal: true },
  gas:            { label: 'Gas',             dark: '#d95926', light: '#eb6834', icon: 'gas',            group: 'gas',     smoke: 0xe6e9ec, thermal: true },
  diesel:         { label: 'Diesel / naphtha',dark: '#8b93a7', light: '#6b7385', icon: 'diesel',         group: 'other',   smoke: 0x8d8f94, thermal: true },
  nuclear:        { label: 'Nuclear',         dark: '#d55181', light: '#e87ba4', icon: 'nuclear',        group: 'nuclear' },
  hydro:          { label: 'Hydro',           dark: '#3987e5', light: '#2a78d6', icon: 'hydro',          group: 'hydro' },
  pumped_storage: { label: 'Pumped storage',  dark: '#3987e5', light: '#2a78d6', icon: 'pumped_storage', group: 'hydro' },
  wind:           { label: 'Wind',            dark: '#199e70', light: '#1baf7a', icon: 'wind',           group: 'wind' },
  solar:          { label: 'Solar',           dark: '#c98500', light: '#eda100', icon: 'solar',          group: 'solar' },
  biomass:        { label: 'Biomass',         dark: '#008300', light: '#008300', icon: 'biomass',        group: 'bio',     smoke: 0xc9c2a8, thermal: true },
  cogen:          { label: 'Bagasse cogen',   dark: '#008300', light: '#008300', icon: 'cogen',          group: 'bio',     smoke: 0xd8d2bc, thermal: true },
  waste:          { label: 'Waste to energy', dark: '#008300', light: '#008300', icon: 'biomass',        group: 'bio',     smoke: 0xa9a9a0, thermal: true },
  battery:        { label: 'Battery storage',         dark: '#8b93a7', light: '#6b7385', icon: 'bolt',           group: 'other' },
};
// chip order = the validated stack order, then the neutrals
export const FUEL_ORDER = ['coal', 'lignite', 'wind', 'gas', 'hydro', 'pumped_storage', 'solar', 'nuclear', 'biomass', 'cogen', 'waste', 'diesel', 'battery'];
// .color follows the UI theme (html[data-theme]); the map layer picks .dark / .light by the basemap under it
export const uiDark = () => document.documentElement.dataset.theme === 'dark';
for (const f of Object.values(FUELS)) Object.defineProperty(f, 'color', { get() { return uiDark() ? this.dark : this.light; }, enumerable: true });
export const fuel = t => FUELS[t] || FUELS.battery;
export const NEUTRAL = { get other() { return uiDark() ? '#8b93a7' : '#6b7385'; }, get import() { return uiDark() ? '#5d6480' : '#8a90a8'; } };

// Transmission voltage classes: one warm ramp (magnitude), most prominent = highest voltage: brightest on
// the night map, darkest on the day map.
export const KV = [
  { key: '765', label: '765 kV', dark: '#fff1a8', light: '#7f2704', w: 3.2 },
  { key: 'hvdc', label: 'HVDC', dark: '#ff9bd2', light: '#8e1f6b', w: 3.0 },
  { key: '400', label: '400 kV', dark: '#ffd84a', light: '#c2410c', w: 2.4 },
  { key: '220', label: '230 / 220 kV', dark: '#e6a23c', light: '#ea8a2e', w: 1.7 },
  { key: '110', label: '110 / 132 kV', dark: '#a8753a', light: '#d9a066', w: 1.1 },
];
