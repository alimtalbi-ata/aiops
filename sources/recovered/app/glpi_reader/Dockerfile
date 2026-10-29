FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY shared /app/shared
COPY glpi_reader /app/glpi_reader
ENV PYTHONPATH=/app
EXPOSE 817
CMD ["uvicorn","glpi_reader.main:app","--host","0.0.0.0","--port","817"]
