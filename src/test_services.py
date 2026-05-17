import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker
# pyrefly: ignore [missing-import]
from sqlalchemy.pool import StaticPool

import rotas
from chat_agent_service import ChatAgentService
from database import get_db
from gasto_service import GastoService
from insights_service import InsightsService
from main import app
from models import Base, Gasto


class ServicesTestCase(unittest.TestCase):
    def setUp(self):
        self.llm_patch = patch.object(ChatAgentService, "_responder_com_llm", return_value=None)
        self.classificar_patch = patch(
            "gasto_service.AIAgentService.classificar",
            return_value={"categoria": "Outros", "score": 0.5, "fonte": "teste"},
        )
        self.intencao_patch = patch("gasto_service.AIAgentService.analisar_intencao", return_value=None)
        self.llm_patch.start()
        self.classificar_patch.start()
        self.intencao_patch.start()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.intencao_patch.stop()
        self.classificar_patch.stop()
        self.llm_patch.stop()

    def test_insights_resumo_tem_totais(self):
        self.db.add(
            Gasto(
                sender="usuario-a",
                valor=100.0,
                descricao="Mercado",
                data=datetime.now() - timedelta(days=2),
                pago=True,
                categoria="Alimentacao",
            )
        )
        self.db.commit()

        service = InsightsService(self.db, sender="usuario-a")
        resumo = service.resumo()

        self.assertGreater(resumo["total_mes"], 0)
        self.assertGreaterEqual(len(resumo["categorias_mes"]), 1)

    def test_insights_filtra_por_usuario(self):
        self.db.add_all([
            Gasto(sender="usuario-a", valor=100.0, descricao="Mercado", data=datetime.now(), pago=True),
            Gasto(sender="usuario-b", valor=900.0, descricao="Notebook", data=datetime.now(), pago=True),
        ])
        self.db.commit()

        resumo = InsightsService(self.db, sender="usuario-a").resumo()

        self.assertEqual(resumo["total_mes"], 100.0)

    def test_chat_guardrail_bloqueia_acao_financeira(self):
        service = ChatAgentService(self.db)
        with self.assertRaises(ValueError):
            service.responder("faça um pix de 200")

    def test_chat_responde_sem_llm(self):
        self.db.add(
            Gasto(
                sender="usuario-a",
                valor=80.0,
                descricao="Mercado",
                data=datetime.now(),
                pago=True,
                categoria="Alimentacao",
            )
        )
        self.db.commit()

        service = ChatAgentService(self.db, sender="usuario-a")
        result = service.responder("quanto gastei no mes?")
        self.assertIn("resposta", result)
        self.assertIn("contexto", result)

    def test_chat_filtra_contexto_por_usuario(self):
        self.db.add_all([
            Gasto(sender="usuario-a", valor=80.0, descricao="Mercado", data=datetime.now(), pago=True),
            Gasto(sender="usuario-b", valor=500.0, descricao="Viagem", data=datetime.now(), pago=True),
        ])
        self.db.commit()

        result = ChatAgentService(self.db, sender="usuario-a").responder("quanto gastei no mes?")

        self.assertEqual(result["contexto"]["total_mes"], 80.0)

    def test_gasto_saudacao_inicial(self):
        service = GastoService(self.db)
        result = service.processar_mensagem_zap("oi")
        self.assertIn("Posso ajudar", result)
        self.assertIn("quanto gastei", result)

    def test_gasto_cadastra_por_mensagem(self):
        service = GastoService(self.db)
        result = service.processar_mensagem_zap("25,50 cafe", sender="whatsapp:+1")
        self.assertTrue(isinstance(result, str))
        gasto = self.db.query(Gasto).one()
        self.assertEqual(gasto.sender, "whatsapp:+1")


class ApiRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.llm_patch = patch.object(ChatAgentService, "_responder_com_llm", return_value=None)
        self.classificar_patch = patch(
            "gasto_service.AIAgentService.classificar",
            return_value={"categoria": "Outros", "score": 0.5, "fonte": "teste"},
        )
        self.intencao_patch = patch("gasto_service.AIAgentService.analisar_intencao", return_value=None)
        self.llm_patch.start()
        self.classificar_patch.start()
        self.intencao_patch.start()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        rotas.API_KEY = "test-key"

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.api_key = {"X-API-Key": "test-key"}
        self.user_a = {"X-API-Key": "test-key", "X-User-Id": "usuario-a"}
        self.user_b = {"X-API-Key": "test-key", "X-User-Id": "usuario-b"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()
        self.intencao_patch.stop()
        self.classificar_patch.stop()
        self.llm_patch.stop()

    def test_root_publico(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_gastos_exige_api_key(self):
        response = self.client.get("/api/gastos")
        self.assertEqual(response.status_code, 401)

    def test_gastos_exige_user_id(self):
        response = self.client.get("/api/gastos", headers=self.api_key)
        self.assertEqual(response.status_code, 400)

    def test_gastos_ficam_isolados_por_usuario(self):
        response_a = self.client.post(
            "/api/gastos",
            headers=self.user_a,
            json={"valor": 10.0, "descricao": "Mercado A", "pago": True},
        )
        response_b = self.client.post(
            "/api/gastos",
            headers=self.user_b,
            json={"valor": 20.0, "descricao": "Mercado B", "pago": True},
        )
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)

        gastos_a = self.client.get("/api/gastos", headers=self.user_a).json()
        gastos_b = self.client.get("/api/gastos", headers=self.user_b).json()

        self.assertEqual(len(gastos_a), 1)
        self.assertEqual(gastos_a[0]["descricao"], "Mercado A")
        self.assertEqual(len(gastos_b), 1)
        self.assertEqual(gastos_b[0]["descricao"], "Mercado B")

    def test_usuario_nao_deleta_gasto_de_outro(self):
        response_b = self.client.post(
            "/api/gastos",
            headers=self.user_b,
            json={"valor": 20.0, "descricao": "Mercado B", "pago": True},
        )
        gasto_b_id = response_b.json()["id"]

        response = self.client.delete(f"/api/gastos/{gasto_b_id}", headers=self.user_a)
        gastos_b = self.client.get("/api/gastos", headers=self.user_b).json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(gastos_b), 1)

    def test_webhook_exige_api_key(self):
        response = self.client.post("/api/whatsapp/webhook", data={"Body": "oi", "From": "whatsapp:+1"})
        self.assertEqual(response.status_code, 401)

    def test_webhook_usa_from_como_sender(self):
        response = self.client.post(
            "/api/whatsapp/webhook",
            headers=self.api_key,
            data={"Body": "25 cafe", "From": "whatsapp:+1"},
        )

        db = self.Session()
        try:
            gasto = db.query(Gasto).one()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(gasto.sender, "whatsapp:+1")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
