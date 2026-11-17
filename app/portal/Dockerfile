FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt "cryptography==46.0.4"
COPY shared /app/shared
COPY portal /app/portal
ENV PYTHONPATH=/app
EXPOSE 777
CMD ["uvicorn","portal.main:app","--host","0.0.0.0","--port","777"]
