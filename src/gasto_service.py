import re
from datetime import datetime

from sqlalchemy.orm import Session

from chat_agent_service import ChatAgentService
from ai_agent_service import AIAgentService
from insights_service import InsightsService
from models import Gasto, WhatsappSession


class GastoService:
    def __init__(self, db: Session):
        self.db = db
        self.ai = AIAgentService()
        self.sender = "unknown"

    def processar_mensagem_zap(self, mensagem: str, sender: str = "") -> str:
        texto = (mensagem or "").strip()
        session = self._get_or_create_session(sender)
        self.sender = session.sender
        
        if not texto:
            texto = "oi"

        lower = texto.lower()
        acao_sistema = None


        if lower == "5" or "insight" in lower or "resumo" in lower:
            acao_sistema = InsightsService(self.db, sender=session.sender).resumo_para_whatsapp()
        elif lower.startswith("pagar "):
            acao_sistema = self._marcar_pago_por_texto(lower)
        elif lower.startswith("limite "):
            acao_sistema = self._definir_limite(session, lower)
        else:
            parsed = self._parse_lancamento(texto)
            if parsed:
                acao_sistema = self._criar_gasto(valor=parsed[0], descricao=parsed[1], pago=True)
            else:
                pendentes = self._get_pendentes_dict()
                intencao = self.ai.analisar_intencao(texto, pendentes)
                
                if intencao:
                    if intencao.get("intencao") == "marcar_pago" and intencao.get("gasto_id"):
                        acao_sistema = self._marcar_pago_por_id(intencao["gasto_id"])
                    elif intencao.get("intencao") == "registrar_gasto" and intencao.get("valor") and intencao.get("descricao"):
                        try:
                            valor = float(intencao["valor"])
                            if valor > 0:
                                p = bool(intencao.get("pago", True))
                                acao_sistema = self._criar_gasto(valor=valor, descricao=str(intencao["descricao"]), pago=p)
                        except ValueError:
                            pass

        try:
            agent = ChatAgentService(self.db, sender=session.sender)
            return agent.responder(texto, acao_sistema=acao_sistema)["resposta"]
        except ValueError as exc:
            return str(exc)

    def _get_or_create_session(self, sender: str) -> WhatsappSession:
        normalized = (sender or "").strip() or "unknown"
        row = self.db.query(WhatsappSession).filter(WhatsappSession.sender == normalized).first()
        if row:
            return row
        row = WhatsappSession(sender=normalized, modo="menu", atualizado_em=datetime.now())
        self.db.add(row)
        self.db.commit()
        return row

    def _parse_lancamento(self, texto: str) -> tuple[float, str] | None:
        match = re.match(r"^\s*(\d+(?:[.,]\d{1,2})?)\s+(.+?)\s*$", texto)
        if match:
            valor = float(match.group(1).replace(",", "."))
            descricao = match.group(2).strip()
            if valor > 0 and descricao:
                return valor, descricao
        return None

    def _criar_gasto(self, valor: float, descricao: str, pago: bool = True) -> str:
        classificacao = self.ai.classificar(descricao=descricao, valor=valor)
        gasto = Gasto(
            sender=self.sender,
            valor=valor,
            descricao=descricao,
            data=datetime.now(),
            pago=pago,
            categoria=classificacao["categoria"],
            classificacao_score=classificacao["score"],
            classificacao_fonte=classificacao["fonte"],
        )
        self.db.add(gasto)
        self.db.commit()
        self.db.refresh(gasto)
        status_pago = "PAGO" if pago else "PENDENTE"
        return (
            f"SISTEMA: Um novo gasto foi registrado com sucesso.\n"
            f"Descricao: {gasto.descricao}\n"
            f"Valor: R$ {gasto.valor:.2f}\n"
            f"Categoria: {gasto.categoria}\n"
            f"Status do Pagamento: {status_pago} (Id: {gasto.id})"
        )

    def _listar_pendentes(self, limite: int = 10) -> str:
        pendentes = (
            self.db.query(Gasto)
            .filter(Gasto.sender == self.sender, Gasto.pago.is_(False))
            .order_by(Gasto.data.desc())
            .limit(limite)
            .all()
        )
        if not pendentes:
            return "Nao ha gastos pendentes."

        linhas = ["Gastos pendentes:"]
        for gasto in pendentes:
            linhas.append(
                f"• {gasto.descricao} | R$ {float(gasto.valor):.2f} 👉 (Para pagar digite: pagar {gasto.id})"
            )
        return "\n".join(linhas)

    def _listar_recentes(self, limite: int = 10) -> str:
        gastos = (
            self.db.query(Gasto)
            .filter(Gasto.sender == self.sender)
            .order_by(Gasto.data.desc())
            .limit(limite)
            .all()
        )
        if not gastos:
            return "Ainda nao existem gastos cadastrados."

        linhas = ["Ultimos gastos:"]
        for gasto in gastos:
            status = "✅ pago" if gasto.pago else "⏳ pendente"
            linhas.append(
                f"• {gasto.descricao} | R$ {float(gasto.valor):.2f} | {status}"
            )
        return "\n".join(linhas)

    def _marcar_pago_por_texto(self, texto: str) -> str:
        try:
            gasto_id = int(texto.replace("pagar", "", 1).strip())
            return self._marcar_pago_por_id(gasto_id)
        except ValueError:
            return "Formato invalido. Use: pagar [número do gasto]"

    def _marcar_pago_por_id(self, gasto_id: int) -> str:
        gasto = self.db.query(Gasto).filter(Gasto.id == gasto_id, Gasto.sender == self.sender).first()
        if not gasto:
            return f"Gasto ID {gasto_id} nao encontrado."
        if gasto.pago:
            return f"O gasto '{gasto.descricao}' (ID {gasto_id}) já estava pago!"

        gasto.pago = True
        self.db.commit()
        return f"✅ O gasto '{gasto.descricao}' (ID {gasto_id}) foi marcado como pago com sucesso!"

    def _get_pendentes_dict(self) -> list[dict]:
        pendentes = (
            self.db.query(Gasto)
            .filter(Gasto.sender == self.sender, Gasto.pago.is_(False))
            .order_by(Gasto.data.desc())
            .limit(15)
            .all()
        )
        return [{"id": g.id, "descricao": g.descricao, "valor": float(g.valor)} for g in pendentes]

    def _definir_limite(self, session: WhatsappSession, texto: str) -> str:
        try:
            valor = float(texto.replace("limite", "", 1).strip().replace(",", "."))
            if valor <= 0:
                raise ValueError
        except ValueError:
            return "Formato invalido. Use: limite <valor> (ex: limite 2000)"
        
        session.limite_mensal = valor
        self.db.commit()
        return f"✅ Limite mensal configurado para R$ {valor:.2f}."




