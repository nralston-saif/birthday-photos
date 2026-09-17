/* Pure collection logic and acknowledged persistence, shared with regression tests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AtlasCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  function merge(base, overlay = {}) {
    const out = clone(base);
    for (const section of ['meta', 'waypoints', 'photos', 'places']) {
      out[section] = out[section] || {};
      for (const [key, value] of Object.entries(overlay[section] || {})) {
        out[section][key] = value && typeof value === 'object'
          ? {...out[section][key], ...value} : value;
      }
    }
    return out;
  }
  function comparePhotos(a, b) {
    return (a.year || 9999) - (b.year || 9999) ||
      (a.date || '').slice(5).localeCompare((b.date || '').slice(5)) || a.file.localeCompare(b.file);
  }
  function resolve(data, edits) {
    const places = data.waypoints.map(w => ({...w, ...edits.waypoints[w.id], files: []}));
    for (const [id, value] of Object.entries(edits.places || {})) {
      if (!places.some(p => p.id === id)) places.push({id, region: '', story: '', ...value, ...edits.waypoints[id], files: []});
    }
    const lookup = new Map(places.map(p => [p.id, p]));
    const baseAssignments = {};
    data.waypoints.forEach(p => p.files.forEach(f => { baseAssignments[f] = p.id; }));
    const photos = Object.entries(data.photos).map(([file, base]) => {
      const e = edits.photos[file] || {};
      const waypoint = own(e, 'waypoint') ? e.waypoint : baseAssignments[file] || '';
      const photo = {...base, ...e, file, waypoint, place: lookup.get(waypoint)};
      if (photo.place) photo.place.files.push(file);
      return photo;
    }).sort(comparePhotos);
    const photoMap = new Map(photos.map(p => [p.file, p]));
    for (const p of places) {
      p.files.sort((a,b) => comparePhotos(photoMap.get(a), photoMap.get(b)));
      p.years = [...new Set(p.files.map(f => photoMap.get(f).year).filter(Boolean))].sort((a,b) => a-b);
      if (!p.files.includes(p.cover)) p.cover = p.files.find(f => photoMap.get(f).caption) || p.files[0];
    }
    places.sort((a,b) => (a.years[0] || 9999) - (b.years[0] || 9999) || a.name.localeCompare(b.name));
    return {places, photos, photoMap, placeMap: lookup, meta: {...data.meta, ...edits.meta}};
  }
  function validateEdits(data, value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Choose an exported writing JSON file.');
    const clean = {meta: {}, photos: {}, waypoints: {}, places: {}};
    for (const section of Object.keys(clean)) {
      const records = value[section] || {};
      if (!records || typeof records !== 'object' || Array.isArray(records)) throw Error('Invalid ' + section + ' section.');
      for (const [id, record] of Object.entries(records)) {
        if (['__proto__','constructor','prototype'].includes(id)) throw Error('Invalid identifier.');
        if (section === 'meta') {
          if (['title','dedication','signature','public_url'].includes(id) && typeof record === 'string') clean.meta[id] = record;
          continue;
        }
        if (!record || typeof record !== 'object' || Array.isArray(record)) throw Error('Invalid record: ' + id);
        if (section === 'photos' && !own(data.photos, id)) throw Error('Unknown photograph: ' + id);
        const fields = section === 'photos' ? ['caption','year','waypoint','placed'] : section === 'places' ? ['name','region','lat','lng'] : ['name','story','cover'];
        clean[section][id] = {};
        for (const key of fields) if (own(record,key)) clean[section][id][key] = record[key];
        if (section === 'photos' && own(record,'year') && record.year !== null && (!Number.isInteger(record.year) || record.year < 1900 || record.year > 2100)) throw Error('Years must be between 1900 and 2100.');
        if (section === 'places' && (!Number.isFinite(record.lat) || Math.abs(record.lat)>85 || !Number.isFinite(record.lng) || Math.abs(record.lng)>180 || typeof record.name !== 'string' || !record.name.trim())) throw Error('Invalid place coordinates or name.');
        for (const key of ['caption','waypoint','name','region','story','cover']) if (own(record,key) && typeof record[key] !== 'string') throw Error('Invalid text in ' + id);
      }
    }
    const ids = new Set([...data.waypoints.map(p => p.id), ...Object.keys(data.edits.places || {}), ...Object.keys(clean.places)]);
    for (const record of Object.values(clean.photos)) if (record.waypoint && !ids.has(record.waypoint)) throw Error('An assigned place is missing.');
    return clean;
  }
  /* Serialize writes. A failed revision remains pending until a successful retry;
     a newer revision arriving during an in-flight write is always written next. */
  function createSaver(write, onStatus, schedule = (fn, ms) => setTimeout(fn, ms)) {
    let current, revision = 0, saved = 0, running = false, failures = 0, retryScheduled = false;
    async function flush() {
      if (running || revision === saved) return;
      running = true;
      onStatus('saving');
      try {
        while (saved < revision) {
          const target = revision, snapshot = clone(current);
          await write(snapshot);
          saved = target;
        }
        failures = 0; onStatus('saved');
      } catch (error) {
        failures++; onStatus('error', error);
        if (failures <= 3 && !retryScheduled) {
          retryScheduled = true;
          schedule(() => { retryScheduled = false; flush(); }, Math.min(8000, 1000 * 2 ** (failures-1)));
        }
      } finally { running = false; }
    }
    return {queue(value) { current = clone(value); revision++; return flush(); }, flush, isDirty: () => saved < revision};
  }
  function findPlaces(places, query) {
    const normalize = text => String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[đĐ]/g, 'd').toLowerCase();
    const words = normalize(query).trim().split(/\s+/).filter(Boolean);
    return places.filter(place => words.every(word => normalize(place.name + ' ' + (place.region || '')).includes(word)));
  }
  return {clone, merge, resolve, comparePhotos, validateEdits, createSaver, findPlaces};
});
