FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seed file if it exists (using wildcard to prevent error if missing, though ideally it should be there)
# Note: Docker COPY fails if file doesn't exist unless using wildcard? 
# Better: Just COPY it. If it fails, the user needs to provide it.
# COPY instance_data_sample.json .

COPY collector_worker .

CMD ["python", "main.py", "--job", "service", "--debug"]
