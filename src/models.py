from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String 
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class WhatsappSession(Base):
    __tablename__ = "whatsapp_sessions"

    sender = Column(String, primary_key=True)  # ex: "whatsapp:+5511999999999"
    modo = Column(String, nullable=False, default="menu")  # "menu" | "assistente"
    limite_mensal = Column(Float, nullable=True)
    atualizado_em = Column(DateTime, default=datetime.now)


class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender = Column(String, nullable=False, default="default")
    valor = Column(Float, nullable=False)
    descricao = Column(String, nullable=False)
    data = Column(DateTime, default=datetime.now)
    pago = Column(Boolean, default=False)
    categoria = Column(String, nullable=True)
    classificacao_score = Column(Float, nullable=True)
    classificacao_fonte = Column(String, nullable=True)


class AgentAuditLog(Base):
    __tablename__ = "agent_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pergunta = Column(String, nullable=False)
    resposta = Column(String, nullable=False)
    origem = Column(String, nullable=False, default="chat")
    criado_em = Column(DateTime, default=datetime.now)