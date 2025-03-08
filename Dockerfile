FROM python:3.10-buster

WORKDIR /app

RUN pip3 install --upgrade pip

COPY requirements.txt .

COPY .env.development  ./

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "5000"]
