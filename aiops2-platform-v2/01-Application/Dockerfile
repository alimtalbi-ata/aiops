FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --system --uid 10001 --create-home appuser
COPY 01-Application/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement /app/requirements.txt
COPY 01-Application/aiops2 /app/aiops2
USER 10001
EXPOSE 8080
CMD ["uvicorn", "aiops2.main:app", "--host", "0.0.0.0", "--port", "8080"]