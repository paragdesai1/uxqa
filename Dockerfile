FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install system deps and Python packages
RUN apt-get update && apt-get install -y curl && \
    pip install --no-cache-dir fastapi uvicorn pillow requests playwright python-multipart && \
    playwright install --with-deps

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
