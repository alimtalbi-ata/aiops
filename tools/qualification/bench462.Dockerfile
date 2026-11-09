# One shared qualification image; application files remain independently hashed.
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=proxy_ca,required=true PIP_CERT=/run/secrets/proxy_ca python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
