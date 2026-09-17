/* One continuous map. The local atlas images remain beneath online detail. */
const AtlasMap = (() => {
  'use strict';
  function create({container, panels, onSelect, onZoom, onMove, onStatus}) {
    if (!window.L) {
      const world = panels.find(p => p.id === 'world'), image = document.createElement('img');
      if (world) { image.src = world.src; image.alt = 'World map'; container.append(image); }
      onStatus('The interactive map could not load. Choose any place to see its photographs.');
      onZoom({min: true, max: true});
      return {setPlaces() {}, showAll() {}, focusPlace() {}, zoom() {}, resize() {}};
    }
    const L = window.L;
    const map = L.map(container, {
      zoomControl: false, minZoom: 0, maxZoom: 18, zoomSnap: 0.25,
      scrollWheelZoom: true, worldCopyJump: true,
      zoomAnimation: !matchMedia('(prefers-reduced-motion: reduce)').matches
    });
    let places = [], signature = '', selected, changing = false, overview = true;
    const markers = new Map();
    const changeView = action => { changing = true; action(); changing = false; };
    // Image bounds use the same Web Mercator projection as the live tiles.
    const fallbackPane = map.createPane('atlasFallback');
    fallbackPane.style.zIndex = '190';
    fallbackPane.style.pointerEvents = 'none';
    for (const panel of panels) {
      L.imageOverlay(panel.src, [[panel.south, panel.west], [panel.north, panel.east]], {
        pane: 'atlasFallback', interactive: false, alt: ''
      }).addTo(map);
    }
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, noWrap: true, referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    let tileErrors = false;
    tiles.on('loading', () => { tileErrors = false; });
    tiles.on('tileerror', () => {
      tileErrors = true;
      onStatus('Some map detail is unavailable. You can still choose any place and see its photographs.');
    });
    tiles.on('load', () => { if (!tileErrors) onStatus(''); });
    map.on('movestart', () => { if (!changing) { overview = false; onMove(); } });
    map.on('zoomend', () => onZoom({min: map.getZoom() <= map.getMinZoom(), max: map.getZoom() >= map.getMaxZoom()}));
    function paintSelection() {
      markers.forEach((marker, id) => {
        const active = id === selected, icon = marker.getElement();
        icon?.classList.toggle('is-selected', active);
        icon?.setAttribute('aria-current', String(active));
        marker.setZIndexOffset(active ? 1000 : 0);
        if (marker.getTooltip().options.permanent !== active) {
          const label = marker.getTooltip().getContent();
          marker.unbindTooltip().bindTooltip(label, {direction: 'top', offset: [0, -13], className: 'place-label', permanent: active});
        }
        if (active) marker.openTooltip(); else marker.closeTooltip();
      });
    }
    function setPlaces(next, id) {
      places = next; selected = id;
      if (!signature) {
        if (places.length) showAll(); else changeView(() => map.setView([20, 0], 1));
      }
      const nextSignature = JSON.stringify(places.map(p => [p.id, p.name, p.lat, p.lng, p.files.length]));
      if (signature !== nextSignature) {
        signature = nextSignature;
        markers.forEach(marker => marker.remove()); markers.clear();
        for (const place of places) {
          const dot = document.createElement('span'); dot.className = 'map-dot';
          const label = document.createElement('span'); label.textContent = place.name;
          const marker = L.marker([place.lat, place.lng], {
            icon: L.divIcon({className: 'memory-pin', html: dot, iconSize: [44, 44], iconAnchor: [22, 22]}),
            title: place.name, keyboard: true, riseOnHover: true
          }).addTo(map).bindTooltip(label, {direction: 'top', offset: [0, -13], className: 'place-label', permanent: false});
          const icon = marker.getElement();
          icon.setAttribute('aria-label', place.name + ', ' + place.files.length + (place.files.length === 1 ? ' photograph' : ' photographs'));
          icon.addEventListener('keydown', event => {
            if (event.key === ' ' || event.key === 'Enter') {
              event.preventDefault(); event.stopPropagation(); onSelect(place.id);
            }
          });
          marker.on('click', () => onSelect(place.id));
          markers.set(place.id, marker);
        }
      }
      paintSelection();
    }
    function showAll() {
      overview = true;
      if (!places.length) return;
      changeView(() => map.fitBounds(places.map(p => [p.lat, p.lng]), {padding: [35, 45], maxZoom: 11, animate: false}));
    }
    function focusPlace(id) {
      const place = places.find(p => p.id === id); if (!place) return;
      overview = false;
      changeView(() => map.setView([place.lat, place.lng], 11, {animate: false}));
      selected = id; paintSelection();
    }
    function resize() {
      changeView(() => map.invalidateSize({animate: false}));
      if (overview) showAll();
    }
    return {setPlaces, showAll, focusPlace, resize, zoom: delta => map.setZoom(map.getZoom() + delta)};
  }
  return {create};
})();
