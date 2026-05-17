from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Gasto, WhatsappSession


class InsightsService:
    def __init__(self, db: Session, sender: str | None = None):
        self.db = db
        self.sender = sender

    def resumo(self) -> dict:
        now = datetime.now()
        inicio_mes = datetime(now.year, now.month, 1)
        inicio_semana = now - timedelta(days=7)

        total_mes = self._total_desde(inicio_mes)
        total_semana = self._total_desde(inicio_semana)
        categorias = self._total_por_categoria(inicio_mes)
        projecao = self._projecao_fim_mes(total_mes, now)
        anomalias = self._anomalias_7_dias()
        
        limite_mensal = None
        if self.sender:
            session = self.db.query(WhatsappSession).filter(WhatsappSession.sender == self.sender).first()
            if session and session.limite_mensal:
                limite_mensal = session.limite_mensal

        return {
            "periodo": {"inicio_mes": inicio_mes.isoformat(), "agora": now.isoformat()},
            "total_semana": round(total_semana, 2),
            "total_mes": round(total_mes, 2),
            "projecao_fim_mes": round(projecao, 2),
            "limite_mensal": round(limite_mensal, 2) if limite_mensal else None,
            "categorias_mes": categorias,
            "anomalias": anomalias,
        }

    def resumo_para_whatsapp(self) -> str:
        data = self.resumo()
        linhas = [
            "📈 *Insights Financeiros*",
            "",
            f"Últimos 7 dias: R$ {data['total_semana']:.2f}",
            f"Mês atual: R$ {data['total_mes']:.2f}",
        ]
        
        if data["limite_mensal"]:
            percentual = (data["total_mes"] / data["limite_mensal"]) * 100
            linhas.append(f"Limite mensal: R$ {data['limite_mensal']:.2f} ({percentual:.1f}% consumido)")
            
        linhas.append(f"Projeção fim do mês: R$ {data['projecao_fim_mes']:.2f}")
        linhas.append("")
        linhas.append("Categorias do mês:")
        for item in data["categorias_mes"][:5]:
            linhas.append(f"- {item['categoria']}: R$ {item['total']:.2f}")
        if data["anomalias"]:
            linhas.append("")
            linhas.append("Possíveis picos:")
            for item in data["anomalias"][:3]:
                linhas.append(
                    f"- {item['descricao']} ({item['fonte']}): R$ {item['valor']:.2f}"
                )
        return "\n".join(linhas)

    def _total_desde(self, inicio: datetime) -> float:
        filters = [Gasto.data >= inicio]
        if self.sender:
            filters.append(Gasto.sender == self.sender)
        total_gastos = (
            self.db.query(func.sum(Gasto.valor))
            .filter(*filters)
            .scalar()
            or 0.0
        )
        return float(total_gastos)

    def _total_por_categoria(self, inicio: datetime) -> list[dict]:
        filters = [Gasto.data >= inicio]
        if self.sender:
            filters.append(Gasto.sender == self.sender)
        rows_gastos = (
            self.db.query(
                func.coalesce(Gasto.categoria, "Outros").label("categoria"),
                func.sum(Gasto.valor).label("total"),
            )
            .filter(*filters)
            .group_by(func.coalesce(Gasto.categoria, "Outros"))
            .all()
        )
        merged: dict[str, float] = {}
        for categoria, total in list(rows_gastos):
            merged[categoria] = merged.get(categoria, 0.0) + float(total or 0.0)

        return [
            {"categoria": categoria, "total": round(total, 2)}
            for categoria, total in sorted(merged.items(), key=lambda x: x[1], reverse=True)
        ]

    def _projecao_fim_mes(self, total_mes: float, now: datetime) -> float:
        dias_passados = max(1, now.day)
        dias_no_mes = 30 if now.month in {4, 6, 9, 11} else (29 if now.month == 2 else 31)
        media = total_mes / dias_passados
        return media * dias_no_mes

    def _anomalias_7_dias(self) -> list[dict]:
        inicio = datetime.now() - timedelta(days=7)
        filters = [Gasto.data >= inicio]
        if self.sender:
            filters.append(Gasto.sender == self.sender)
        media_gastos = (
            self.db.query(func.avg(Gasto.valor))
            .filter(*filters)
            .scalar()
            or 0.0
        )
        limite = float(media_gastos) * 2.5
        if limite <= 0:
            return []

        picos_gastos = (
            self.db.query(Gasto.descricao, Gasto.valor)
            .filter(*filters, Gasto.valor > limite)
            .limit(5)
            .all()
        )
        result = []
        for descricao, valor in picos_gastos:
            result.append({"fonte": "gasto_manual", "descricao": descricao, "valor": float(valor)})
        return result
