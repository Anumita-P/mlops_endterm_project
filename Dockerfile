FROM apache/airflow:2.8.1-python3.11

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies
RUN pip install --no-cache-dir \
    pandas==2.0.3 \
    numpy==1.24.3 \
    scikit-learn==1.3.0 \
    requests==2.31.0 \
    dvc==3.31.1 \
    mlflow==2.13.0 \
    psycopg2-binary==2.9.9 \
    python-dotenv==1.0.0

WORKDIR /home/airflow