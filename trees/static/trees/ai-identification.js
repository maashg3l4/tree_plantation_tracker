document.addEventListener('DOMContentLoaded', () => {
    const imageInput = document.getElementById('id_image');
    const speciesInput = document.getElementById('id_species');
    const status = document.getElementById('species-analysis-status');
    const resultCard = document.getElementById('species-results');
    const warning = document.getElementById('species-analysis-warning');
    const providerNote = document.getElementById('species-provider-note');
    const predictionsList = document.getElementById('species-predictions');
    if (!imageInput || !speciesInput || !status || !resultCard) return;

    let requestId = 0;
    imageInput.addEventListener('change', async () => {
        const image = imageInput.files[0];
        requestId += 1;
        const currentRequest = requestId;
        resultCard.hidden = true;
        status.className = 'species-analysis-status';
        if (!image) {
            status.textContent = '';
            return;
        }
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(image.type)) {
            status.classList.add('species-analysis-status--error');
            status.textContent = 'Choose a JPEG, PNG, or WebP image to identify its species.';
            return;
        }

        status.classList.add('species-analysis-status--loading');
        status.textContent = 'Analyzing image…';
        const payload = new FormData();
        payload.append('image', image);
        payload.append('csrfmiddlewaretoken', document.querySelector('#tree-form [name=csrfmiddlewaretoken]').value);
        try {
            const response = await fetch(document.getElementById('tree-form').dataset.identifyUrl, {
                method: 'POST',
                body: payload,
            });
            const result = await response.json();
            if (currentRequest !== requestId) return;
            if (!response.ok || !result.success) throw new Error(result.error || 'Species identification failed.');
            predictionsList.replaceChildren();
            warning.hidden = true;
            providerNote.textContent = result.provider === 'plantnet'
                ? 'Identified with PlantNet.'
                : result.provider === 'inaturalist'
                    ? 'Identified with iNaturalist.'
                    : 'No confident species match; enter the species manually.';
            result.predictions.forEach((prediction, index) => {
                const row = document.createElement('li');
                const name = document.createElement('span');
                const confidence = document.createElement('span');
                const useButton = document.createElement('button');
                name.textContent = prediction.name;
                confidence.className = 'species-confidence';
                confidence.textContent = prediction.confidence === null
                    ? 'Community match'
                    : `${Math.round(prediction.confidence * 100)}% match`;
                useButton.type = 'button';
                useButton.className = 'species-use-button';
                useButton.textContent = index === 0 ? 'Use this' : 'Pick this';
                useButton.addEventListener('click', () => {
                    speciesInput.value = prediction.name;
                    speciesInput.dispatchEvent(new Event('input', { bubbles: true }));
                    speciesInput.focus();
                    status.textContent = `Species set to ${prediction.name}.`;
                });
                row.append(name, confidence, useButton);
                predictionsList.append(row);
            });
            const topConfidence = result.predictions[0]?.confidence;
            if (!result.predictions.length || (topConfidence !== null && topConfidence < 0.6)) {
                warning.textContent = 'AI is unsure. Please confirm the species manually.';
                warning.hidden = false;
            }
            resultCard.hidden = false;
            status.textContent = result.predictions.length
                ? 'Species suggestions are ready. Choose a match or enter the species yourself.'
                : 'No species match was found. You can still enter the species manually.';
        } catch (error) {
            if (currentRequest !== requestId) return;
            status.classList.add('species-analysis-status--error');
            status.textContent = `${error.message} You can still enter the species manually.`;
        }
    });
});
