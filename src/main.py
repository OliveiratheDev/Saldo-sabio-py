from pathlib import Path
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import logging

from database import criar_tabelas, SessionLocal
from rotas import router
from models import Gasto
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

app = FastAPI()
app.include_router(router)


async def monitorar_lembretes():
    logging.info("Monitor de lembretes iniciado em segundo plano!")
    while True:
        try:
            # Verifica a cada 30 segundos para ser rápido e preciso
            await asyncio.sleep(30)
            
            # Se não tem credenciais válidas do Twilio, pula
            if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or "insira_seu" in TWILIO_AUTH_TOKEN or not TWILIO_AUTH_TOKEN.strip():
                continue
                
            db = SessionLocal()
            try:
                agora = datetime.now()
                # Busca lembretes/gastos pendentes e vencidos não notificados
                pendentes = (
                    db.query(Gasto)
                    .filter(
                        Gasto.pago.is_(False),
                        Gasto.notificado.is_(False),
                        Gasto.data <= agora
                    )
                    .all()
                )
                
                if pendentes:
                    from twilio.rest import Client
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    
                    for gasto in pendentes:
                        destinatario = gasto.sender
                        if destinatario and destinatario.startswith("whatsapp:"):
                            mensagem_texto = (
                                f"Oi! 😊 Passando para te lembrar que você tem uma conta pendente: "
                                f"*{gasto.descricao}* no valor de *R$ {gasto.valor:.2f}*. Não esquece de pagar, hein? 💸"
                            )
                            try:
                                client.messages.create(
                                    body=mensagem_texto,
                                    from_=TWILIO_NUMBER,
                                    to=destinatario
                                )
                                logging.info(f"Notificação proativa enviada com sucesso para {destinatario}!")
                            except Exception as tw_err:
                                logging.error(f"Erro ao enviar notificação Twilio: {tw_err}")
                            
                            gasto.notificado = True
                    
                    db.commit()
            except Exception as db_err:
                logging.error(f"Erro no banco de dados durante monitoramento: {db_err}")
            finally:
                db.close()
                
        except Exception as loop_err:
            logging.error(f"Erro crítico no loop do monitor de lembretes: {loop_err}")


@app.on_event("startup")
def startup():
    criar_tabelas()
    asyncio.create_task(monitorar_lembretes())

@app.get("/")
def inicio():
    return {
        "mensagem": "Saldo Sábio API funcionando!",
    }