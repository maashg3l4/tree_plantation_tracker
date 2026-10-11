import base64
import hashlib
import json
import logging
import mimetypes
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
REQUEST_TIMEOUT = 18


class AIServiceError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def _image_bytes(image):
    if getattr(image, 'size', None) and image.size > MAX_IMAGE_BYTES:
        raise AIServiceError('Image must be 10 MB or smaller.', status_code=400)
    content_type = (
        getattr(image, 'content_type', None)
        or getattr(image, 'mime_type', None)
        or mimetypes.guess_type(getattr(image, 'name', ''))[0]
    )
    if content_type not in IMAGE_TYPES:
        raise AIServiceError('Upload a JPEG, PNG, or WebP image.', status_code=400)
    image.seek(0)
    data = image.read(MAX_IMAGE_BYTES + 1)
    image.seek(0)
    if len(data) > MAX_IMAGE_BYTES:
        raise AIServiceError('Image must be 10 MB or smaller.', status_code=400)
    if not data:
        raise AIServiceError('The selected image is empty.', status_code=400)
    return data, content_type


def image_digest(image):
    data, _ = _image_bytes(image)
    return hashlib.sha256(data).hexdigest()


def _post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'TreePlantationTracker/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        logger.warning('AI provider returned HTTP %s', error.code)
        raise AIServiceError('The image analysis provider could not process this image.') from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning('AI provider request failed: %s', error)
        raise AIServiceError('Image analysis is temporarily unavailable. Please try again.') from error


def _post_image(url, data, content_type, extra_fields=None, file_field='images'):
    boundary = f'----tree-tracker-{hashlib.sha256(data[:64]).hexdigest()[:24]}'
    parts = [
        (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{file_field}"; filename="tree-image"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode('utf-8'),
        data,
        b'\r\n',
    ]
    for name, value in (extra_fields or {}).items():
        parts.append(
            (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f'{value}\r\n'
            ).encode('utf-8')
        )
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    request = Request(
        url,
        data=b''.join(parts),
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'User-Agent': 'TreePlantationTracker/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        logger.warning('Species provider returned HTTP %s', error.code)
        raise AIServiceError('The species identification provider could not process this image.') from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning('Species provider request failed: %s', error)
        raise AIServiceError('Species identification is temporarily unavailable. Please try again.') from error


def _plantnet_identification(data, content_type):
    if not settings.PLANTNET_API_KEY:
        return None
    result = _post_image(
        f'{settings.PLANTNET_API_URL}/identify/all?{urlencode({"api-key": settings.PLANTNET_API_KEY})}',
        data,
        content_type,
        extra_fields={'organs': 'auto'},
    )
    predictions = sorted(
        result.get('results', []),
        key=lambda item: item.get('score', 0),
        reverse=True,
    )
    output = []
    for item in predictions:
        species = item.get('species', {})
        name = species.get('scientificNameWithoutAuthor') or species.get('scientificName')
        if name:
            output.append({'name': name, 'confidence': float(item.get('score', 0))})
        if len(output) == 3:
            break
    if not output:
        return None
    return {'provider': 'plantnet', 'predictions': output}


def _inat_identification(data, content_type):
    result = _post_image(
        f'{settings.INATURALIST_API_URL}/computervision/score_image',
        data,
        content_type,
        file_field='image',
    )
    predictions = []
    for item in result.get('results', []):
        taxon = item.get('taxon') or {}
        name = taxon.get('preferred_common_name') or taxon.get('name')
        if name:
            predictions.append({'name': name, 'confidence': float(item.get('score', 0))})
        if len(predictions) == 3:
            break
    if not predictions:
        return None
    return {'provider': 'inaturalist', 'predictions': predictions}


def identify_species(image):
    data, content_type = _image_bytes(image)
    failures = []
    if settings.PLANTNET_API_KEY:
        try:
            prediction = _plantnet_identification(data, content_type)
            if prediction:
                prediction['image_hash'] = hashlib.sha256(data).hexdigest()
                return prediction
        except AIServiceError as error:
            failures.append(str(error))
    try:
        prediction = _inat_identification(data, content_type)
    except AIServiceError as error:
        failures.append(str(error))
        prediction = None
    if prediction:
        prediction['image_hash'] = hashlib.sha256(data).hexdigest()
        return prediction
    if failures:
        raise AIServiceError('Species identification providers are unavailable. Please enter the species manually.')
    return {'provider': 'none', 'predictions': [], 'image_hash': hashlib.sha256(data).hexdigest()}


def analyze_tree_health(image):
    data, content_type = _image_bytes(image)
    if not settings.GEMINI_API_KEY:
        raise AIServiceError(
            'Tree health analysis is not configured. Ask an administrator to set GEMINI_API_KEY.'
        )
    encoded = base64.b64encode(data).decode('ascii')
    payload = {
        'contents': [
            {
                'parts': [
                    {
                        'text': (
                            'Assess only visible signs in this tree image. The result is educational, '
                            'not a professional diagnosis. Return JSON with score (integer 0-100), issues '
                            '(array of short strings), recommendations (array of actionable short strings), '
                            'and confidence (number 0-1). Do not infer hidden diseases; when the image is '
                            'unclear, use low confidence and say so in issues.'
                        ),
                    },
                    {'inline_data': {'mime_type': content_type, 'data': encoded}},
                ],
            }
        ],
        'generationConfig': {
            'temperature': 0,
            'responseMimeType': 'application/json',
            'responseSchema': {
                'type': 'OBJECT',
                'properties': {
                    'score': {'type': 'INTEGER'},
                    'issues': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                    'recommendations': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                    'confidence': {'type': 'NUMBER'},
                },
                'required': ['score', 'issues', 'recommendations', 'confidence'],
            },
        },
    }
    result = _post_json(
        f'{settings.GEMINI_API_URL}/models/{settings.GEMINI_VISION_MODEL}:generateContent'
        f'?{urlencode({"key": settings.GEMINI_API_KEY})}',
        payload,
    )
    try:
        content = ''.join(
            part.get('text', '')
            for part in result['candidates'][0]['content']['parts']
        )
        analysis = json.loads(content)
        score = analysis['score']
        confidence = analysis['confidence']
        issues = analysis['issues']
        recommendations = analysis['recommendations']
        if (
            isinstance(score, bool)
            or not isinstance(score, int)
            or not 0 <= score <= 100
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
            or not isinstance(issues, list)
            or not all(isinstance(item, str) for item in issues)
            or not isinstance(recommendations, list)
            or not all(isinstance(item, str) for item in recommendations)
        ):
            raise ValueError('Model response fields are invalid.')
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        logger.warning('Gemini returned an invalid tree health analysis')
        raise AIServiceError('The image analysis returned an invalid result. Please try again.') from error
    return {
        'score': score,
        'issues': issues[:10],
        'recommendations': recommendations[:10],
        'confidence': float(confidence),
        'model_used': settings.GEMINI_VISION_MODEL[:40],
        'image_hash': hashlib.sha256(data).hexdigest(),
    }
