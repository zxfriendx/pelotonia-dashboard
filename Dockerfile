FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests pillow

COPY app/ app/

# GCP Cloud Run: DB is baked into the image (copied above from app/)
# K8s: DB lives on a PersistentVolume, set PELOTONIA_DB=/data/pelotonia_data.db
EXPOSE 8080

CMD ["python", "app/dashboard.py", "--port", "8080", "--host", "0.0.0.0"]
