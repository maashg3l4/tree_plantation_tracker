document.addEventListener("DOMContentLoaded", () => {
  const mapElement = document.getElementById("plot-map");
  const boundaryInput = document.getElementById("id_boundary");
  if (!mapElement || !boundaryInput || !window.L || !window.L.Control.Draw) return;

  const map = L.map(mapElement).setView([23.685, 90.3563], 7);
  const street = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  });
  const satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles &copy; Esri", maxZoom: 18 },
  );
  street.addTo(map);
  L.control.layers({ Street: street, Satellite: satellite }).addTo(map);

  const boundaries = new L.FeatureGroup();
  map.addLayer(boundaries);
  map.addControl(
    new L.Control.Draw({
      draw: {
        polygon: { allowIntersection: false, showArea: true },
        polyline: false,
        rectangle: false,
        circle: false,
        circlemarker: false,
        marker: false,
      },
      edit: { featureGroup: boundaries, remove: true },
    }),
  );

  function syncBoundary() {
    const geojson = boundaries.toGeoJSON();
    boundaryInput.value = geojson.features.length
      ? JSON.stringify(geojson.features[0].geometry)
      : "";
  }

  map.on(L.Draw.Event.CREATED, (event) => {
    boundaries.clearLayers();
    boundaries.addLayer(event.layer);
    syncBoundary();
  });
  map.on(L.Draw.Event.EDITED, syncBoundary);
  map.on(L.Draw.Event.DELETED, syncBoundary);

  document.getElementById("plot-form").addEventListener("submit", (event) => {
    if (!boundaryInput.value) {
      event.preventDefault();
      const error = document.getElementById("map-boundary-error");
      error.hidden = false;
      error.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
});
