FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run as a non-root, unprivileged user; no host docker socket, no extra caps.
RUN useradd -m labuser
USER labuser

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
