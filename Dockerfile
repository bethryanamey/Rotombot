FROM python:3.10
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt
WORKDIR /app
COPY . .
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
ENTRYPOINT ["streamlit", "run", "app/rotombot_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]