# ---------------------------------------------------------------------------
# TicketTriage API - local container image.
#
# This image exists to satisfy the "container learning evidence" part of the
# brief. It is built and run LOCALLY ONLY. Do not push it to Azure Container
# Registry, App Service, or Container Apps: those are not free-tier safe for
# this project, and the deployed app uses Static Web Apps managed functions.
#
#   docker build -t tickettriage-api .
#   docker run --rm -p 7071:80 --env-file .env tickettriage-api
#   curl http://localhost:7071/api/health
# ---------------------------------------------------------------------------

FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_RUNTIME=python

WORKDIR /home/site/wwwroot

# Install dependencies first so Docker can cache this layer.
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the function app itself.
COPY api/ .

EXPOSE 80
