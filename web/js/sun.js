// Where the sun is, minute by minute (NOAA's low-precision solar position, ±0.1° over this century),
// and the night side of the map as pixel blocks: civil twilight (sun 0..-6°), nautical (-6..-12°) and
// night (below -12°), on a 0.25° grid. Sunset crosses India east to west in about two hours, north-east
// India first.
const rad = Math.PI / 180;

export function sunPosition(date = new Date()) {
  const jd = date.getTime() / 86400000 + 2440587.5, n = jd - 2451545.0;
  const L = (280.46 + 0.9856474 * n) % 360, g = ((357.528 + 0.9856003 * n) % 360) * rad;
  const lambda = (L + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * rad;
  const eps = (23.439 - 0.0000004 * n) * rad;
  const dec = Math.asin(Math.sin(eps) * Math.sin(lambda));
  const ra = Math.atan2(Math.cos(eps) * Math.sin(lambda), Math.cos(lambda));
  const gmst = (18.697374558 + 24.06570982441908 * n) % 24;              // hours
  // longitude where the sun is overhead right now
  const subLon = ((ra / rad - gmst * 15 + 540) % 360) - 180;
  return { dec, subLat: dec / rad, subLon };
}

// sun altitude (degrees) and azimuth (degrees from north, clockwise) at a place
export function sunAt(lat, lon, pos = sunPosition()) {
  const H = (lon - pos.subLon) * rad, phi = lat * rad, d = pos.dec;
  const sinAlt = Math.sin(phi) * Math.sin(d) + Math.cos(phi) * Math.cos(d) * Math.cos(H);
  const alt = Math.asin(Math.max(-1, Math.min(1, sinAlt)));
  const az = Math.atan2(-Math.sin(H), Math.tan(d) * Math.cos(phi) - Math.sin(phi) * Math.cos(H));
  return { alt: alt / rad, az: ((az / rad) + 360) % 360 };
}

// GeoJSON of the dark side over [w, s, e, n], one rectangle per run of cells in the same band per row
export function nightBands(bbox = [55, -2, 105, 40], step = 0.25, pos = sunPosition()) {
  const [w, s, e, n] = bbox, feats = [];
  const band = alt => (alt >= 0 ? 0 : alt > -6 ? 1 : alt > -12 ? 2 : 3);
  for (let lat = s; lat < n; lat += step) {
    let runStart = w, runBand = band(sunAt(lat + step / 2, w + step / 2, pos).alt);
    for (let lon = w + step; lon <= e + 1e-9; lon += step) {
      const b = lon >= e ? -1 : band(sunAt(lat + step / 2, lon + step / 2, pos).alt);
      if (b !== runBand) {
        if (runBand > 0) feats.push({ type: 'Feature', properties: { b: runBand },
          geometry: { type: 'Polygon', coordinates: [[[runStart, lat], [lon, lat], [lon, lat + step], [runStart, lat + step], [runStart, lat]]] } });
        runStart = lon; runBand = b;
      }
    }
  }
  return { type: 'FeatureCollection', features: feats };
}

// sunrise / sunset (Date) for a place today, by stepping the altitude through the day (1-minute accuracy)
export function sunTimes(lat, lon, day = new Date()) {
  const t0 = new Date(day); t0.setUTCHours(0, 0, 0, 0);
  let rise = null, set = null, prev = sunAt(lat, lon, sunPosition(t0)).alt;
  for (let m = 1; m <= 1440; m++) {
    const t = new Date(t0.getTime() + m * 60000), a = sunAt(lat, lon, sunPosition(t)).alt;
    if (prev < -0.833 && a >= -0.833) rise = t;
    if (prev >= -0.833 && a < -0.833) set = t;
    prev = a;
  }
  return { rise, set };
}
