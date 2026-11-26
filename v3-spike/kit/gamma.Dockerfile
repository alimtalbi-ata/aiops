FROM python:3.13-slim
WORKDIR /lab
COPY vertical /lab/vertical
COPY kit/gamma-container.py /lab/gamma-container.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN mkdir /audit && chown 1000:1000 /audit && chmod 0700 /audit
USER 1000:1000
EXPOSE 18080
ENTRYPOINT ["python","/lab/gamma-container.py"]
