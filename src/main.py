from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import logging

from database import criar_tabelas
from rotas import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

app = FastAPI()
app.include_router(router)

@app.on_event("startup")
def startup():
    criar_tabelas()

@app.get("/")
def inicio():
    return {
        "mensagem": "Saldo Sábio API funcionando!",
    }