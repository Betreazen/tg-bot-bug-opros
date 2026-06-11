FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY phrases.json .
COPY app/ ./app/

CMD ["python", "-m", "app.main"]
