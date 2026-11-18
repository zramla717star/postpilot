# PostPilot — Hugging Face Spaces (Docker, free CPU, no card needed).
# HF sets PORT=7860; the app reads HOST and PORT from the environment.
FROM python:3.12-slim
WORKDIR /app
COPY . .
EXPOSE 7860
CMD ["python3", "app.py"]
