# docker/app/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app .

# Expose the port Uvicorn will listen on
EXPOSE 8000

# Command to run Uvicorn
# Using gunicorn as a process manager for uvicorn workers is a common best practice
CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
