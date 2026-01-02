FROM python:3.11-slim

WORKDIR /app

COPY collector_frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY collector_frontend .

# Streamlit uses port 8501 by default
EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
