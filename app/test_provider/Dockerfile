FROM python:3.12-slim
WORKDIR /app
# The qualification lab uses umask 077 when archiving sources. The
# non-root runtime must never inherit mode 0600 from build context.
COPY --chmod=0644 test_provider/main.py /app/main.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 818
CMD ["python","/app/main.py"]
