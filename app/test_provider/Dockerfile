FROM python:3.12-slim
WORKDIR /app
COPY test_provider/main.py /app/main.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 818
CMD ["python","/app/main.py"]
