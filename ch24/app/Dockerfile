# The checkout offer service as a container (Chapter 19), for Cloud Run or any container platform.
# Build from the repository root:  docker build -f app/Dockerfile -t checkout-offer .
FROM python:3.11-slim
WORKDIR /srv
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt
COPY app/ app/
ENV PORT=8080
# Runs as a non-root user; it needs no file system writes.
RUN useradd --uid 10001 --no-create-home offer
USER offer
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
