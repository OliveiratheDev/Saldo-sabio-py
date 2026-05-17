import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

class AIAgentService:
    def __init__(self):
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

    def gerar_resposta(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    
    def responder(self, pergunta: str) -> dict:
        resposta = self.gerar_resposta(pergunta)
        return {"resposta": resposta}
        
    def classificar(self, descricao: str, valor: float) -> dict:
        prompt = f"""Classifique este gasto: "{descricao}" no valor de R$ {valor}.
        Retorne um JSON com as chaves "categoria" (ex: Alimentação, Transporte, Saúde, Moradia, Lazer, Outros) e "score" (confiança de 0.0 a 1.0)."""
        
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content.strip())
            return {
                "categoria": data.get("categoria", "Outros"),
                "score": float(data.get("score", 0.5)),
                "fonte": "openai"
            }
        except Exception:
            return {
                "categoria": "Outros",
                "score": 0.5,
                "fonte": "fallback"
            }
    def analisar_intencao(self, texto: str, pendentes: list[dict]) -> dict | None:
        from datetime import datetime
        prompt = f"""O usuário enviou a seguinte mensagem: "{texto}".
        Você precisa identificar a intenção dele. Você tem a seguinte lista de gastos pendentes:
        {json.dumps(pendentes, ensure_ascii=False)}
        
        Horário de Referência atual do sistema do usuário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (fuso local).
        
        Regras:
        1. Se a intenção for PAGAR, QUITAR ou BAIXAR um gasto pendente existente (ou seja, ele diz que já pagou a conta de luz, etc), retorne o JSON: {{"intencao": "marcar_pago", "gasto_id": ID_AQUI}}
        2. Se a intenção for REGISTRAR/CADASTRAR um gasto NOVO ou criar um LEMBRETE/AGENDAMENTO de pagamento futuro (ex: "me lembre de pagar X", "agendar pix de Y"), determine se ele já foi pago pela forma como foi escrito. Retorne o JSON: {{"intencao": "registrar_gasto", "valor": VALOR_FLOAT, "descricao": "DESCRICAO", "pago": BOOLEAN, "data_lembrete": "YYYY-MM-DDTHH:MM:SS" ou null}}.
           - Se o usuário mencionar uma data, horário ou prazo futuro (ex: "às 20:04", "daqui a dois dias", "na terça-feira", "dia 20"), calcule o momento exato desse lembrete com base no Horário de Referência acima e inclua no campo "data_lembrete" no formato ISO-8601 "YYYY-MM-DDTHH:MM:SS". Além disso, inclua obrigatoriamente essa informação diretamente no campo "descricao" (ex: "Boleto (às 20:04)", "Pix para o João (na terça-feira)").
           - Se não houver horário nem data específica futura, retorne "data_lembrete": null.
           - Se for um lembrete, agendamento ou conta futura (ex: "me lembre de", "agendar", "boleto", "vence", "conta de", "pra pagar", "pendente"), o valor de "pago" DEVE ser false.
           - Se ele disser "gastei", "comprei", "paguei", "cartão", "ifood", "uber", o valor de "pago" DEVE ser true.
           - Em caso de dúvida, assuma "pago": true.
        3. Se não for nenhuma das duas (ex: perguntas gerais, conversas), retorne: {{"intencao": "outros"}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content.strip())
            return data
        except Exception:
            return None