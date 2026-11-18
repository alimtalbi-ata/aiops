FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY shared /app/shared
COPY portal /app/portal
COPY --from=noc_scripts /aiops2_noc_decision.py /aiops2_noc_decision_html.py /aiops2_event_correlation.py /aiops2_digital_twin_impact.py /aiops2_analyst_critic.py /scripts/
ENV PYTHONPATH=/app
EXPOSE 777
CMD ["uvicorn","portal.main:app","--host","0.0.0.0","--port","777"]
