FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY services/station-reservation/app.py ./app.py
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8001"]
