from sqlalchemy.orm import Session

class OpenFinanceService:
    """
    Serviço base preparado para futura integração de Open Finance.
    Aqui ficarão as chamadas para APIs bancárias (Pluggy, Belvo, etc)
    para buscar contas, saldos e transações automaticamente.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def get_authorization_url(self, user_id: str) -> str:
        """Retorna o link para o usuário autorizar o acesso ao banco."""
        # TODO: Implementar geração de link de consentimento
        pass

    def sync_accounts(self, user_id: str):
        """Busca e atualiza as contas vinculadas do usuário."""
        # TODO: Implementar sincronização de contas
        pass

    def fetch_recent_transactions(self, user_id: str):
        """Busca as transações recentes e cadastra como Gasto no sistema."""
        # TODO: Implementar sincronização de gastos automáticos
        pass
