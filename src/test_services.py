import unittest
from datetime import datetime, timedelta

# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker

from chat_agent_service import ChatAgentService
from gasto_service import GastoService
from insights_service import InsightsService
from models import Base, Gasto, TransacaoOpenFinance


class ServicesTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_insights_resumo_tem_totais(self):
        self.db.add(
            Gasto(
                valor=100.0,
                descricao="Mercado",
                data=datetime.now() - timedelta(days=2),
                pago=True,
                categoria="Alimentacao",
            )
        )
        self.db.add(
            TransacaoOpenFinance(
                provider_transaction_id="tx-1",
                descricao="Uber",
                valor=50.0,
                data=datetime.now() - timedelta(days=1),
                categoria="Transporte",
            )
        )
        self.db.commit()

        service = InsightsService(self.db)
        resumo = service.resumo()

        self.assertGreater(resumo["total_mes"], 0)
        self.assertGreaterEqual(len(resumo["categorias_mes"]), 1)

    def test_chat_guardrail_bloqueia_acao_financeira(self):
        service = ChatAgentService(self.db)
        with self.assertRaises(ValueError):
            service.responder("faça um pix de 200")

    def test_chat_responde_sem_llm(self):
        self.db.add(
            Gasto(
                valor=80.0,
                descricao="Mercado",
                data=datetime.now(),
                pago=True,
                categoria="Alimentacao",
            )
        )
        self.db.commit()

        service = ChatAgentService(self.db)
        result = service.responder("quanto gastei no mes?")
        self.assertIn("resposta", result)
        self.assertIn("contexto", result)

    def test_gasto_saudacao_inicial(self):
        service = GastoService(self.db)
        result = service.processar_mensagem_zap("oi")
        self.assertIn("Sábio", result)
        self.assertIn("ajudar", result)

    def test_gasto_cadastra_por_mensagem(self):
        service = GastoService(self.db)
        result = service.processar_mensagem_zap("25,50 cafe")
        # O retorno é do ChatAgentService (LLM), que interceptou a acao de sistema
        self.assertTrue(isinstance(result, str))
        self.assertEqual(self.db.query(Gasto).count(), 1)


if __name__ == "__main__":
    unittest.main()
