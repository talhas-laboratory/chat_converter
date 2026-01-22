FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=pwuser:pwuser . /app

# Ensure output directory exists and is writable
RUN mkdir -p /app/output && chmod -R 777 /app/output

USER pwuser

EXPOSE 8080 8090

CMD ["sh", "-c", "uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8080}"]

