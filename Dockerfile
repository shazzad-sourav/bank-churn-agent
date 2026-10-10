FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m churn_agent.database
EXPOSE 8501
# Pass your key at run time: docker run -p 8501:8501 --env-file .env bank-churn-agent
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
