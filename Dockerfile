FROM python:3.10

# Install ODBC Driver for SQL Server
RUN apt-get update && \
    apt-get install -y apt-transport-https && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# Install SQL Server tools
RUN ACCEPT_EULA=Y apt-get install -y mssql-tools
# Add the SQL Server tools directory to the PATH
ENV PATH="$PATH:/opt/mssql-tools/bin"

COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt
COPY ./app /app
WORKDIR /app
EXPOSE 443
HEALTHCHECK CMD curl --fail http://localhost:443/_stcore/health
ENTRYPOINT ["streamlit", "run", "rotombot_streamlit.py", "--server.port=443", "--server.address=0.0.0.0"]