FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY shared /app/shared
COPY integration /app/integration
ENV PYTHONPATH=/app
EXPOSE 817
CMD ["uvicorn","integration.main:app","--host","0.0.0.0","--port","817"]
