from roleta.models import MembroClube, RegraPontuacao, ExtratoPontuacao
from django.utils import timezone

class GamificationService:
    @staticmethod
    def atribuir_pontos(membro: MembroClube, gatilho: str, descricao_extra: str = "") -> tuple:
        """
        Adiciona pontos de Saldo e XP a um membro baseado em um gatilho cadastrado.
        Retorna (sucesso, mensagem)
        """
        try:
            regra = RegraPontuacao.objects.get(gatilho=gatilho, ativo=True)
        except RegraPontuacao.DoesNotExist:
            return False, f"Regra inativa ou inexistente para gatilho: {gatilho}"

        # Verificar limites
        if regra.limite_por_membro > 0:
            qtd_vezes_ganhas = ExtratoPontuacao.objects.filter(membro=membro, regra=regra).count()
            if qtd_vezes_ganhas >= regra.limite_por_membro:
                return False, f"Membro já atingiu o limite para a regra: {regra.nome_exibicao}"

        # Efetivar a pontuação do Gatilho
        novo_saldo = membro.saldo + regra.pontos_saldo
        novo_xp = membro.xp_total + regra.pontos_xp
        
        membro.saldo = novo_saldo
        membro.xp_total = novo_xp
        membro.save()

        # Registrar o extrato de pontuação
        ExtratoPontuacao.objects.create(
            membro=membro,
            regra=regra,
            pontos_saldo_ganhos=regra.pontos_saldo,
            pontos_xp_ganhos=regra.pontos_xp,
            descricao_extra=descricao_extra
        )

        return True, f"Ganhou {regra.pontos_saldo} saldo e {regra.pontos_xp} XP."
