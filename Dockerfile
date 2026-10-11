FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind.config.js ./
COPY trees/templates ./trees/templates
COPY trees/static_src ./trees/static_src
COPY trees/static/trees/app.js ./trees/static/trees/app.js
RUN npm run build:css

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=assets /app/trees/static/trees/app.css ./trees/static/trees/app.css
RUN python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn tracker.wsgi:application --bind 0.0.0.0:8000"]
