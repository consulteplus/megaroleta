from django.db import models

class Cidade(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nome
        
    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        ordering = ['nome']

class PremioRoleta(models.Model):
    nome = models.CharField(max_length=255)
    quantidade = models.IntegerField(default=0)
    posicoes = models.CharField(max_length=50, help_text="Posições na roleta (ex: 4,7)", default="1")
    probabilidade = models.IntegerField(default=1, help_text="Peso da probabilidade (ex: 1 para raro, 10 para comum)")
    cidades_permitidas = models.ManyToManyField(Cidade, blank=True, related_name="premios", help_text="Selecione as cidades permitidas. Se deixar vazio, o prêmio valerá para QUALQUER cidade.")

    def __str__(self):
        cidades = ", ".join([c.nome for c in self.cidades_permitidas.all()]) if self.id and self.cidades_permitidas.exists() else "Todas"
        return f"{self.nome} ({cidades}) - {self.quantidade} restando"

    class Meta:
        verbose_name = "Prêmio da Roleta"
        verbose_name_plural = "Prêmios da Roleta"

class RouletteAsset(models.Model):
    ASSET_TYPES = [
        ('frame', 'Frame da Roleta'),
        ('background', 'Fundo da Página'),
        ('logo', 'Logo Central'),
        ('pointer', 'Ponteiro/Seta'),
    ]
    tipo = models.CharField(max_length=20, choices=ASSET_TYPES, default='frame')
    ordem = models.IntegerField(default=0, help_text="0-12 para frames")
    imagem = models.ImageField(upload_to='roleta/assets/')
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'ordem']
        verbose_name = "Asset da Roleta"
        verbose_name_plural = "Assets da Roleta"

class RoletaConfig(models.Model):
    custo_giro = models.IntegerField(default=10, help_text="Pontos necessários para girar a roleta")
    xp_por_giro = models.IntegerField(default=5, help_text="Quantidade de XP ganha a cada giro da roleta")
    nome_clube = models.CharField(max_length=100, default="Clube MegaLink")

    def __str__(self):
        return f"Configurações do {self.nome_clube}"

    class Meta:
        verbose_name = "Configuração da Roleta"
        verbose_name_plural = "Configurações da Roleta"

class NivelClube(models.Model):
    nome = models.CharField(max_length=50, help_text="Ex: Bronze, Prata, Ouro")
    xp_necessario = models.IntegerField(default=0, help_text="XP mínimo para alcançar este nível")
    ordem = models.IntegerField(default=1, help_text="Ordem de exibição (1 é o mais baixo)")

    def __str__(self):
        return f"Nível {self.ordem}: {self.nome} ({self.xp_necessario} XP)"

    class Meta:
        ordering = ['ordem']
        verbose_name = "Nível do Clube"
        verbose_name_plural = "Níveis do Clube"


class MembroClube(models.Model):
    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=14, unique=True)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    cep = models.CharField(max_length=10, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    saldo = models.IntegerField(default=0, help_text="Saldo acumulado de pontos (Giros)")
    xp_total = models.IntegerField(default=0, help_text="Experiência acumulada (Define o Nível)")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    id_cliente_hubsoft = models.IntegerField(null=True, blank=True)
    validado = models.BooleanField(default=False, help_text="Se o membro já validou o OTP")

    @property
    def nivel_atual(self):
        nivel = NivelClube.objects.filter(xp_necessario__lte=self.xp_total).order_by('-xp_necessario').first()
        return nivel.nome if nivel else "Iniciante"

    @property
    def proximo_nivel(self):
        prox = NivelClube.objects.filter(xp_necessario__gt=self.xp_total).order_by('xp_necessario').first()
        return prox

    def __str__(self):
        return f"{self.nome} ({self.cpf})"

    class Meta:
        verbose_name = "Membro do Clube"
        verbose_name_plural = "Membros do Clube"

class RegraPontuacao(models.Model):
    gatilho = models.CharField(max_length=50, unique=True, help_text="Identificador único (ex: cadastro, indicacao)")
    nome_exibicao = models.CharField(max_length=100, help_text="Ex: Bônus de Boas Vindas")
    pontos_saldo = models.IntegerField(default=0, help_text="Quantos Giros/Saldo a pessoa ganha")
    pontos_xp = models.IntegerField(default=0, help_text="Quanto XP a pessoa ganha")
    limite_por_membro = models.IntegerField(default=1, help_text="Quantas vezes um mesmo membro pode ganhar? (0 para iimitado)")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome_exibicao} ({self.pontos_saldo} Saldo | {self.pontos_xp} XP)"

    class Meta:
        verbose_name = "Regra de Pontuação"
        verbose_name_plural = "Regras de Pontuação"

class ExtratoPontuacao(models.Model):
    membro = models.ForeignKey(MembroClube, on_delete=models.CASCADE, related_name='extratos')
    regra = models.ForeignKey(RegraPontuacao, on_delete=models.CASCADE)
    pontos_saldo_ganhos = models.IntegerField(default=0)
    pontos_xp_ganhos = models.IntegerField(default=0)
    descricao_extra = models.CharField(max_length=255, null=True, blank=True, help_text="Ex: Indicou CPF 123456789")
    data_recebimento = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.membro.nome} - {self.regra.nome_exibicao} ({self.data_recebimento.strftime('%d/%m/%Y')})"

    class Meta:
        verbose_name = "Extrato de Pontuação"
        verbose_name_plural = "Extratos de Pontuação"


class ParticipanteRoleta(models.Model):
    STATUS_CHOICES = [
        ('reservado', 'Reservado'),
        ('ganhou', 'Ganhou'),
        ('inviavel_tec', 'Inviável Tecnicamente'),
        ('inviavel_cani', 'Inviável Cani'),
    ]

    membro = models.ForeignKey(MembroClube, on_delete=models.CASCADE, related_name='giros', null=True, blank=True)
    nome = models.CharField(max_length=255, null=True, blank=True)
    cpf = models.CharField(max_length=14)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    cep = models.CharField(max_length=10, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    premio = models.CharField(max_length=255)
    canal_origem = models.CharField(max_length=100, default='Online')
    perfil_cliente = models.CharField(max_length=10, default='nao')
    id_cliente_hubsoft = models.IntegerField(null=True, blank=True)
    saldo = models.IntegerField(default=0, help_text="Saldo de pontos do membro")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='reservado')
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.premio}"

    class Meta:
        verbose_name = "Participante da Roleta"
        verbose_name_plural = "Participantes da Roleta"
