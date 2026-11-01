(() => {
    const form = document.getElementById('tree-form');
    const mapElement = document.getElementById('map');
    if (!form || !mapElement) return;

    const country = document.getElementById('id_country');
    const division = document.getElementById('id_division');
    const district = document.getElementById('id_district');
    const otherLocation = document.getElementById('id_other_location');
    const latitude = document.getElementById('id_latitude');
    const longitude = document.getElementById('id_longitude');
    const location = document.getElementById('id_location');
    const status = document.getElementById('tree-map-status');

    const readChoices = (id) => {
        const element = document.getElementById(id);
        if (!element) return {};
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error(`Could not read ${id}.`, error);
            return {};
        }
    };
    const divisions = readChoices('tree-divisions-data');
    const districts = readChoices('tree-districts-data');

    const fillSelect = (select, choices, selected = '', placeholder = 'Select an option') => {
        const options = choices?.length ? choices : [['', placeholder]];
        select.disabled = !choices?.length;
        select.replaceChildren(...options.map(([value, label]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            option.selected = value === selected;
            return option;
        }));
    };

    const selectedDivision = division.dataset.selected || '';
    const selectedDistrict = district.dataset.selected || '';
    fillSelect(division, divisions[country.value], selectedDivision, 'Choose a country first');
    fillSelect(district, districts[division.value], selectedDistrict, 'Choose a division first');

    const updateLocation = () => {
        const parts = [country.value, division.value, district.value, otherLocation.value]
            .map((part) => part.trim())
            .filter(Boolean);
        location.value = parts.join(', ') || (
            latitude.value && longitude.value ? `${latitude.value}, ${longitude.value}` : ''
        );
    };

    country.addEventListener('change', () => {
        fillSelect(division, divisions[country.value], '', 'No region list available');
        fillSelect(district, districts[division.value], '', 'Choose a division first');
        updateLocation();
    });
    division.addEventListener('change', () => {
        fillSelect(district, districts[division.value], '', 'No district list available');
        updateLocation();
    });
    [district, otherLocation].forEach((field) => {
        field.addEventListener('input', updateLocation);
        field.addEventListener('change', updateLocation);
    });

    const fallbackCenter = [23.8103, 90.4125];
    let map;
    let marker;
    let tileErrors = 0;
    let tilesReady = false;

    const updateCoordinates = (point) => {
        latitude.value = point.lat.toFixed(6);
        longitude.value = point.lng.toFixed(6);
        latitude.dispatchEvent(new Event('input', { bubbles: true }));
        longitude.dispatchEvent(new Event('input', { bubbles: true }));
        latitude.setCustomValidity('');
        longitude.setCustomValidity('');
        updateLocation();
        if (status) status.textContent = 'Location pinned. You can drag the marker or edit the coordinates.';
    };

    const positionMarker = (lat, lng) => {
        if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
            return false;
        }
        const point = { lat, lng };
        if (marker) marker.setLatLng(point);
        else {
            marker = L.marker(point, {
                draggable: true,
                icon: L.divIcon({
                    className: 'tree-map-pin',
                    html: '<span></span>',
                    iconSize: [24, 30],
                    iconAnchor: [12, 28],
                }),
            }).addTo(map);
            marker.on('dragend', () => updateCoordinates(marker.getLatLng()));
        }
        map.panTo(point);
        return true;
    };

    const updateMapTheme = () => {
        const style = document.documentElement.classList.contains('dark') ? 'dark_all' : 'light_all';
        const tileUrl = style === 'dark_all'
            ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'
            : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
        tileErrors = 0;
        tilesReady = false;
        map.eachLayer((layer) => {
            if (layer instanceof L.TileLayer) map.removeLayer(layer);
        });
        const tileLayer = L.tileLayer(tileUrl, {
            attribution: style === 'dark_all'
                ? 'Tiles &copy; <a href="https://www.esri.com/">Esri</a>, DeLorme, NAVTEQ, and NPS'
                : 'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Sources: Esri, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS user community',
            maxZoom: 19,
            crossOrigin: true,
        });
        tileLayer.on('tileload', () => {
            tilesReady = true;
            if (status && tileErrors === 0) status.textContent = 'Move the map pin to the tree’s location.';
        });
        tileLayer.on('tileerror', () => {
            tileErrors += 1;
            if (!tilesReady && status) {
                status.textContent = 'Map imagery is unavailable right now. You can still enter coordinates below.';
            }
        });
        tileLayer.addTo(map);
    };

    if (!window.L) {
        if (status) status.textContent = 'Interactive map could not load. Enter the planting coordinates below instead.';
    } else {
        try {
            map = L.map(mapElement, { scrollWheelZoom: false, zoomControl: true })
                .setView(fallbackCenter, 12);
            L.control.scale({ imperial: false }).addTo(map);
            map.on('click', (event) => {
                positionMarker(event.latlng.lat, event.latlng.lng);
                updateCoordinates(event.latlng);
            });
            updateMapTheme();
            new MutationObserver(updateMapTheme).observe(document.documentElement, {
                attributes: true,
                attributeFilter: ['class'],
            });
            window.setTimeout(() => map.invalidateSize(), 100);
            window.addEventListener('resize', () => map.invalidateSize());

            if (latitude.value && longitude.value) {
                const lat = Number(latitude.value);
                const lng = Number(longitude.value);
                if (!positionMarker(lat, lng) && status) {
                    status.textContent = 'Saved coordinates are invalid. Enter a latitude and longitude to place the pin.';
                }
            }
        } catch (error) {
            console.error('The planting map could not be initialized.', error);
            if (status) status.textContent = 'Interactive map could not load. Enter the planting coordinates below instead.';
        }
    }

    const updateFromCoordinateFields = () => {
        if (!latitude.value && !longitude.value) {
            latitude.setCustomValidity('');
            longitude.setCustomValidity('');
            return;
        }
        const lat = Number(latitude.value);
        const lng = Number(longitude.value);
        const valid = latitude.value !== '' && longitude.value !== ''
            && Number.isFinite(lat) && Number.isFinite(lng)
            && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
        latitude.setCustomValidity(valid ? '' : 'Enter a valid latitude and longitude pair.');
        longitude.setCustomValidity(valid ? '' : 'Enter a valid latitude and longitude pair.');
        if (valid && map) positionMarker(lat, lng);
        if (valid) {
            updateLocation();
            if (status) status.textContent = 'Coordinates saved. The pin shows your selected location.';
        }
    };
    [latitude, longitude].forEach((field) => {
        field.addEventListener('change', updateFromCoordinateFields);
        field.addEventListener('blur', updateFromCoordinateFields);
    });

    form.addEventListener('submit', () => {
        updateLocation();
        if (!location.value && latitude.value && longitude.value) {
            location.value = `${latitude.value}, ${longitude.value}`;
        }
    });
})();
