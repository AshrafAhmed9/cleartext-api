FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install CPU torch for the container (no GPU in Docker by default)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Download model during build, not at runtime
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='unitary/toxic-bert', top_k=None)"

COPY . .

CMD ["celery", "-A", "core.celery_app", "worker", "--loglevel=info", "--pool=solo", "--concurrency=2"]
