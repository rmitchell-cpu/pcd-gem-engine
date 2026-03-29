FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    anthropic>=0.40.0 \
    "pydantic>=2.0" \
    pymupdf>=1.24.0 \
    python-dateutil>=2.9.0 \
    python-dotenv>=1.0.0 \
    "supabase>=2.0.0" \
    "psycopg2-binary>=2.9.0" \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.20.0" \
    "python-multipart>=0.0.6" \
    "jinja2>=3.1.0"

# Copy application code
COPY . .

# Railway sets PORT env var
ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn web.app:app --host 0.0.0.0 --port ${PORT}
