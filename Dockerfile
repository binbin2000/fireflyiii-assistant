FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY main.py .

RUN useradd -m -u 1000 app && chown -R app /app
USER app

EXPOSE 8000

CMD ["python", "main.py", "--no-browser", "--host", "0.0.0.0"]
