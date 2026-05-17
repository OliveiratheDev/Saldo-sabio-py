import unicodedata
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from models import AgentAuditLog, Gasto, WhatsappSession

class ChatAgentService:
    def __init__(self, db: Session, sender: str | None = None):
        self.db = db
        self.sender = sender

    def responder(self, pergunta: str, acao_sistema: str = None) -> dict:
        self._validar_pergunta(pergunta)
        enviar_resumo_completo = self._verificar_e_atualizar_envio_resumo()
        contexto = self._gerar_contexto()
        resposta = self._responder_com_llm(pergunta, contexto, acao_sistema, enviar_resumo_completo) or self._responder_local(
            pergunta, contexto
        )
        self._auditar(pergunta=pergunta, resposta=resposta, origem="chat")
        return {"resposta": resposta, "contexto": contexto}

    def _verificar_e_atualizar_envio_resumo(self) -> bool:
        if not self.sender:
            return True
        session = self.db.query(WhatsappSession).filter(WhatsappSession.sender == self.sender).first()
        if not session:
            return True
            
        agora = datetime.now()
        ultimo = session.ultimo_resumo_em
        
        # Se nunca enviou ou o último envio foi em um dia diferente
        if not ultimo or (ultimo.year != agora.year or ultimo.month != agora.month or ultimo.day != agora.day):
            session.ultimo_resumo_em = agora
            self.db.commit()
            return True
            
        return False

    def _validar_pergunta(self, pergunta: str):
        if not pergunta or not pergunta.strip():
            raise ValueError("Sua mensagem está vazia. Pode repetir?")
        lower = pergunta.lower()
        # Se for um pedido de lembrete ou agendamento, não bloqueia pelo guardrail
        if "lembr" in lower or "agend" in lower:
            return
        bloqueios = ["faça um pix", "fazer pix", "enviar pix", "realizar pix", "transferir din", "fazer transfer", "realizar pag"]
        if any(token in lower for token in bloqueios):
            raise ValueError(
                "Guardrail: este agente apenas analisa dados e nao executa operacoes financeiras."
            )

    def _gerar_contexto(self) -> dict:
        agora = datetime.now()
        inicio_mes = datetime(agora.year, agora.month, 1)
        inicio_semana = agora - timedelta(days=7)
        inicio_mes_anterior, fim_mes_anterior = self._intervalo_mes_anterior(agora)

        total_gastos_mes = self._sum_gastos(inicio=inicio_mes, fim=None)
        total_mes = float(total_gastos_mes)

        total_mes_anterior = float(
            self._sum_gastos(inicio=inicio_mes_anterior, fim=fim_mes_anterior)
        )

        total_semana = self._sum_gastos(inicio=inicio_semana, fim=None)

        top_categorias_mes = self._top_categorias(inicio=inicio_mes, fim=None, limit=5)
        
        limite_mensal = None
        if self.sender:
            session = self.db.query(WhatsappSession).filter(WhatsappSession.sender == self.sender).first()
            if session and session.limite_mensal:
                limite_mensal = session.limite_mensal

        pendentes_query = self.db.query(Gasto).filter(Gasto.pago.is_(False))
        if self.sender:
            pendentes_query = pendentes_query.filter(Gasto.sender == self.sender)
        pendentes = (
            pendentes_query
            .order_by(Gasto.data.desc())
            .limit(10)
            .all()
        )
        pendentes_list = [{"id": g.id, "descricao": g.descricao, "valor": float(g.valor)} for g in pendentes]

        recentes_query = self.db.query(Gasto)
        if self.sender:
            recentes_query = recentes_query.filter(Gasto.sender == self.sender)
        recentes = recentes_query.order_by(Gasto.data.desc()).limit(5).all()
        recentes_list = [{"descricao": g.descricao, "valor": float(g.valor), "pago": g.pago, "data": g.data.strftime("%d/%m/%Y")} for g in recentes]

        return {
            "agora": agora.isoformat(),
            "total_mes": round(total_mes, 2),
            "total_semana": round(float(total_semana), 2),
            "total_mes_anterior": round(total_mes_anterior, 2),
            "delta_mes_vs_anterior": round(total_mes - total_mes_anterior, 2),
            "limite_mensal": round(limite_mensal, 2) if limite_mensal else None,
            "top_categorias_mes": top_categorias_mes,
            "gastos_pendentes": pendentes_list,
            "ultimos_5_gastos": recentes_list
        }
        
          

    def _normalizar(self, texto: str) -> str:
        return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8").lower()

    def _responder_local(self, pergunta: str, contexto: dict) -> str:
        
        q = self._normalizar(pergunta or "")

        if "semana" in q:
            return f"Nos ultimos 7 dias, seus gastos somam R$ {contexto['total_semana']:.2f}."

        if self._quer_comparar_mes(q):
            return (
                f"Mes atual: R$ {contexto['total_mes']:.2f}\n"
                f"Mes anterior: R$ {contexto['total_mes_anterior']:.2f}\n"
                f"Diferenca: R$ {contexto['delta_mes_vs_anterior']:.2f}"
            )

        if "mes" in q:
            return f"No mes atual, o total acumulado e R$ {contexto['total_mes']:.2f}."

        if any(token in q for token in ["top categorias", "principais categorias", "categorias principais"]):
            linhas = self._formatar_top_categorias(contexto.get("top_categorias_mes") or [])
            return linhas

        if "categoria" in q:
            if not contexto.get("top_categorias_mes"):
                return "Ainda nao ha categorias suficientes para analise."
            top = contexto["top_categorias_mes"][0]
            return f"Sua categoria com maior gasto no mes e {top['categoria']}, com R$ {top['total']:.2f}."

        termo = self._extrair_termo_busca(q)
        if termo:
            agora = datetime.now()
            inicio_mes = datetime(agora.year, agora.month, 1)
            total_termo = self._sum_por_termo(termo=termo, inicio=inicio_mes, fim=None)
            if total_termo <= 0:
                return f"Neste mes, nao encontrei gastos com '{termo}'."
            return f"Neste mes, voce gastou R$ {total_termo:.2f} com '{termo}'."

        return (
            "Posso ajudar com:\n"
            "- total da semana: 'quanto gastei na semana?'\n"
            "- total do mes: 'quanto gastei no mes?'\n"
            "- comparar meses: 'compare com o mes passado'\n"
            "- top categorias: 'top categorias do mes'\n"
            "- busca: 'quanto gastei em mercado?'"
        )

    def _responder_com_llm(self, pergunta: str, contexto: dict, acao_sistema: str = None, enviar_resumo_completo: bool = True) -> str | None:
        if not OPENAI_API_KEY:
            return None
            
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
        texto_acao = f"\n\nACAO DE SISTEMA EXECUTADA NOS BASTIDORES:\n{acao_sistema}\nPor favor, informe isso ao usuário de forma amigável e comemore/confirme se foi um sucesso." if acao_sistema else ""
        
        prompt = (
            "Você é o Saldo Sábio, um assistente financeiro muito simpático, parceiro e amigável. "
            "Responda de forma extremamente natural, humana, leve e conversacional, como se fosse um parceiro de finanças conversando no WhatsApp. Use emojis adequados! "
            "IMPORTANTE 1: Analise o total_mes, o limite_mensal e o delta_mes_vs_anterior no Contexto. Se o usuário estiver gastando muito (ex: ultrapassando ou chegando perto do limite, ou com o delta muito alto em relação ao mês passado), dê um 'puxão de orelha' divertido e parceiro! Reclame que ele tá gastando demais, mande ele segurar a emoção no cartão, mas sempre de forma bem-humorada, tipo um amigo dando bronca. "
            "IMPORTANTE 2: Ao apresentar valores, contas ou relatórios, seja MUITO visual e direto. Use listas (bullet points), negrito nos valores (ex: *R$ 50,00*) e frases curtas. Facilite a leitura para que o usuário entenda só de bater o olho, sem precisar ler parágrafos longos. "
            "IMPORTANTE 3 (RESTRIÇÃO DE RESUMO DIÁRIO): Se a variável 'enviar_resumo_completo' for False E a mensagem atual envolver o registro de um novo gasto ou lembrete (ou seja, se houver ACAO DE SISTEMA executada), você DEVE retornar APENAS uma confirmação super curta, natural, leve e amigável do gasto registrado. NUNCA adicione o resumo do mês, delta, top categorias ou puxão de orelha nessa resposta curta. O resumo financeiro e o puxão de orelha só devem ser enviados se 'enviar_resumo_completo' for True OU se o usuário fez uma pergunta direta sobre seu orçamento/limite (ex: 'quanto gastei?', 'meus pendentes', 'limite'). "
            "Não execute operações, apenas informe sobre os dados fornecidos no contexto ou confirme a ação que acabou de ser feita. "
            "O contexto inclui as categorias, limites, últimos gastos que o usuário teve e contas pendentes que ele não pagou ainda. Use SOMENTE o contexto JSON abaixo para basear sua resposta.\n\n"
            f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}{texto_acao}\n\n"
            f"enviar_resumo_completo (relatório e bronca diária permitidos agora?): {'Sim' if enviar_resumo_completo else 'Não'}\n\n"
            f"Pergunta do usuário: {pergunta}"
        )
        
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception:
            return None

    def _auditar(self, pergunta: str, resposta: str, origem: str):
        row = AgentAuditLog(pergunta=pergunta, resposta=resposta, origem=origem)
        self.db.add(row)
        self.db.commit()

    def _sum_gastos(self, inicio: datetime, fim: datetime | None) -> float:
        q = self.db.query(func.sum(Gasto.valor)).filter(Gasto.data >= inicio)
        if self.sender:
            q = q.filter(Gasto.sender == self.sender)
        if fim:
            q = q.filter(Gasto.data < fim)
        return float(q.scalar() or 0.0)



    def _top_categorias(self, inicio: datetime, fim: datetime | None, limit: int = 5) -> list[dict]:
        categorias: dict[str, float] = {}

        q_g = self.db.query(
            func.coalesce(Gasto.categoria, "Outros").label("categoria"),
            func.sum(Gasto.valor).label("total"),
        ).filter(Gasto.data >= inicio)
        if self.sender:
            q_g = q_g.filter(Gasto.sender == self.sender)
        if fim:
            q_g = q_g.filter(Gasto.data < fim)
        for c, t in q_g.group_by(func.coalesce(Gasto.categoria, "Outros")).all():
            categorias[str(c)] = categorias.get(str(c), 0.0) + float(t or 0.0)



        ordenado = sorted(categorias.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"categoria": c, "total": round(float(t), 2)} for c, t in ordenado]

    def _sum_por_termo(self, termo: str, inicio: datetime, fim: datetime | None) -> float:
        like = f"%{termo}%"
        total = 0.0

        q_g = self.db.query(func.sum(Gasto.valor)).filter(Gasto.data >= inicio).filter(Gasto.descricao.ilike(like))
        if self.sender:
            q_g = q_g.filter(Gasto.sender == self.sender)
        if fim:
            q_g = q_g.filter(Gasto.data < fim)
        total += float(q_g.scalar() or 0.0)



        return float(total)

    def _intervalo_mes_anterior(self, agora: datetime) -> tuple[datetime, datetime]:
        inicio_mes_atual = datetime(agora.year, agora.month, 1)
        fim_mes_anterior = inicio_mes_atual
        ultimo_dia_mes_anterior = fim_mes_anterior - timedelta(days=1)
        inicio_mes_anterior = datetime(ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month, 1)
        return inicio_mes_anterior, fim_mes_anterior

    def _quer_comparar_mes(self, q: str) -> bool:
        return any(token in q for token in ["mes passado", "mês passado", "compar", "anterior"])

    def _extrair_termo_busca(self, q: str) -> str | None:
        # Exemplos: "quanto gastei em mercado", "gastei quanto no ifood"
        m = re.search(r"\b(?:gastei\s+quanto|quanto\s+gastei)\s+(?:em|no|na)\s+(.+)$", q)
        if not m:
            return None
        termo = m.group(1).strip()
        termo = re.sub(r"[?.!]+$", "", termo).strip()
        if not termo or len(termo) < 2:
            return None
        return termo

    def _formatar_top_categorias(self, rows: list[dict]) -> str:
        if not rows:
            return "Ainda nao ha categorias suficientes para analise."
        linhas = ["Top categorias do mes:"]
        for i, row in enumerate(rows, start=1):
            linhas.append(f"{i}. {row['categoria']}: R$ {float(row['total']):.2f}")
        return "\n".join(linhas)
 