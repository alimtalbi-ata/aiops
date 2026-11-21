FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY shared /app/shared
COPY evidence /app/evidence
ENV PYTHONPATH=/app
EXPOSE 812
CMD ["uvicorn","evidence.main:app","--host","0.0.0.0","--port","812"]
