FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r -s /bin/false appuser

WORKDIR /app

COPY pyproject.toml .
RUN mkdir -p src/eol_tool && echo '__version__ = "0.0.0"' > src/eol_tool/__init__.py
RUN pip install --no-cache-dir ".[api]"

RUN playwright install chromium

COPY . .
RUN pip install --no-cache-dir -e . --no-deps

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "eol_tool.api:app", "--host", "0.0.0.0", "--port", "8080"]
