FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py core.py ./
ENV PYTHONUNBUFFERED=1 DATABASE_PATH=/app/data/ctf.sqlite3
CMD ["python", "bot.py"]
