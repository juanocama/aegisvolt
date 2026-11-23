FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY services/billing-wallet/app.py ./app.py
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8002","--no-access-log"]
