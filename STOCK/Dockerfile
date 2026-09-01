FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (build-essential needed for lightgbm and others)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libomp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn
RUN python -m nltk.downloader vader_lexicon stopwords punkt

# Copy source code
COPY . .

# Expose port
EXPOSE 5051

# Run the API via gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5051", "--timeout", "300", "--workers", "1", "stock_api:app"]
