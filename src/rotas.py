import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from chat_agent_service import ChatAgentService
from config import API_KEY
from database import get_db
from gasto_service import GastoService
from insights_service import InsightsService
from models import Gasto

def validar_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if not API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida")


def validar_api_key_webhook(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = None,
):
    key = x_api_key or api_key
    if not API_KEY:
        return
    if not key or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida")


def get_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=400, detail="X-User-Id é obrigatório")
    return x_user_id.strip()


router = APIRouter()
public_router = APIRouter(prefix="/api")
api_router = APIRouter(prefix="/api", dependencies=[Depends(validar_api_key)])


class GastoPayload(BaseModel):
    valor: float
    descricao: str
    data: datetime | None = None
    pago: bool = False


class ChatPayload(BaseModel):
    pergunta: str


@public_router.post("/whatsapp/webhook", response_class=Response)
def receber_whatsapp(
    body: str = Form(default="", alias="Body"),
    sender: str = Form(default="", alias="From"),
    db: Session = Depends(get_db),
    _ = Depends(validar_api_key_webhook),
):
    service = GastoService(db)
    resposta = service.processar_mensagem_zap(body, sender=sender)
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{resposta}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


@api_router.get("/gastos")
def listar_todos(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    return db.query(Gasto).filter(Gasto.sender == user_id).all()


@api_router.get("/gastos/pendentes")
def listar_pendentes(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    return db.query(Gasto).filter(Gasto.sender == user_id, Gasto.pago.is_(False)).all()


@api_router.post("/gastos")
def salvar(gasto: GastoPayload, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    novo = Gasto(
        sender=user_id,
        valor=gasto.valor,
        descricao=gasto.descricao,
        data=gasto.data or datetime.now(),
        pago=gasto.pago,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@api_router.delete("/gastos/{gasto_id}")
def deletar(gasto_id: int, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id, Gasto.sender == user_id).first()
    if gasto:
        db.delete(gasto)
        db.commit()
    return {"ok": True}



@api_router.get("/insights/resumo")
def resumo_insights(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    service = InsightsService(db, sender=user_id)
    return service.resumo()


@api_router.post("/agent/chat")
def chat_agente(payload: ChatPayload, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    service = ChatAgentService(db, sender=user_id)
    try:
        return service.responder(payload.pergunta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


router.include_router(public_router)
router.include_router(api_router)
