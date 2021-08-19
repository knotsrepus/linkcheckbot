FROM mcr.microsoft.com/playwright:focal

RUN adduser linkcheckbot
USER linkcheckbot

COPY . /app
WORKDIR /app

RUN python3 -m pip install -r requirements.txt
RUN python3 -m playwright install chromium
RUN python3 -m pip install .

# In minutes
ENV MAX_CACHE_AGE=1440
ENV RULESET_UPDATE_INTERVAL=1440

CMD ["python3", "main.py"]
