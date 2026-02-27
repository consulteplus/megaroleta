🎰 Mega Sorteio Roleta
Uma Plataforma Interativa de Engajamento e Premiação

Visão Geral • Arquitetura • Recursos • Integrações • Banco de Dados • Segurança • Instalação

📖 Visão Geral
O Mega Sorteio Roleta é um sistema completo em Python/Django desenhado para campanhas de marketing conversacional e fidelização de clientes. O projeto vai muito além de uma simples roleta visual: ele atua como um sistema robusto de captação de leads (com enriquecimento de dados), verificação anti-fraude em tempo real e análise de métricas para gestores.

Neste projeto, o cliente interage com uma roleta de prêmios animada. Antes de girar, ele fornece seu número (ou CPF), resultando em um fluxo dinâmico dependendo se ele é um "Novo Cliente" ou "Membro do Clube".

🏗️ Arquitetura e Tecnologias
A aplicação segue o padrão de arquitetura monolítica moderna, com backend renderizando os templates de base, mas utilizando uma abordagem de Frontend Desacoplado (Decoupled) na engine principal da roleta, onde o Javascript nativo se comunica com endpoints JSON do Django.

Stack Tecnológica
Linguagem Principal: Python 3.10+
Framework Web: Django (com foco no ORM, Sessions e Admin Interno)
Frontend:
HTML5 e CSS3 (Design Responsivo e Neomórfico)
JavaScript (Vanilla API para chamadas fetch, gerenciamento de fluxo no index_frontend.html)
Animação da Roleta via Canvas / Transitions CSS
Bibliotecas: jQuery (para InputMasks de CPF/CEP/Mobile), SweetAlert2 (Alertas Estilizados), Chart.js (Painel Administrativo)
Banco de Dados: SQLite3 (Ambiente Dev) / PostgreSQL (Produção)
Persistência de Mídia: Django Media Storage (para manipulação de avatares, imagens da roleta e ícones)
✨ Recursos Principais
Fluxo do Cliente (Front-End)
Identificação Dinâmica: O usuário digita seu telefone.
Separação de Leads: A API checa se é um usuário conhecido ou não. Se for novo, pede CPF, CEP e preenche automaticamente o resto dos dados se possuir correspondência na base via Hubsoft.
Validação de Identidade: Todos os novos cadastros/jogares devem provar que são donos do número através de um webhook enviado por n8n (One-Time Password - OTP).
Roleta Inteligente: O giro visual (animação angular fluida e responsiva com foco UI/UX) não decide nada aleatoriamente no front. Assim que o jogador clica em iniciar, o backend roda o algoritmo ponderado, seleciona o prêmio, debita da contagem global, sincroniza e informa a interface onde a roda deve parar de girar.
🎮 Gamificação e Retenção (Clube MegaLink)
Sistema de Níveis (XP): Jogadores ganham pontos de Experiência (XP) ao realizar ações, subindo de Patentes (ex: Bronze, Prata, Ouro), construindo engajamento de longo prazo.
Missões Interativas (Quests): Um painel inline estilizado fornece missões para o cliente (ex: "Pagar fatura adiantada", "Baixar APP"). Ao cumpri-las, ele recebe recompensas automáticas de mais Giros na roleta e XP.
Dashboard do Jogador Aprimorado: O perfil do usuário foi desenhado com foco num UI Premium, split-screen (50/50), destacando a roleta com um botão flutuante e exibindo claramente na lateral a progressão do seu nível e cartões de missões disponíveis.
📊 Dashboard Administrativo (Visão Gerencial)
A interface de administração estendida do Django foi customizada para ter a página /roleta/dashboard/.

Funil de Venda/Conversão: Conta perfeitamente a queda entre "Iniciados", "Validados (WhatsApp)" e "Jogadores Ativos".
Kpis Diários (Line Chart): Gráficos criados com Chart.js mostrando como os jogadores estão gastando as rodadas na linha do tempo dos últimos 7 dias.
Share de Saída (Doughnut Chart): Divisão exata dos prêmios mais sorteados, tudo integrado ao ORM em tempo real views.py.
Feed ao vivo: Tabela dos últimos ganhadores em tempo real.
🔗 Integrações Externas
Para elevar o projeto, o backend orquestra chamadas cruciais durante os milissegundos do cadastro:

n8n (Motor de Automação / WhatsApp):
Na linha views.solicitar_otp(), o Django dispara um requests.post contra um Webhook do N8N enviando { numero, validacao }. Isso aciona a mensagem no celular do cliente para provar sua capacidade de contato (evitando disparos curtos via script de bad actors).
Hubsoft (ERP do Provedor de Internet):
Na linha views.verificar_cliente(), caso seja um novo número, a aplicação confere o client_id na API interna da empresa. Se achar, ela herda as informações verdadeiras e simplifica o frontend do usuário, cortando em até 80% o tempo para girar.
ViaCEP API:
Resolução básica de CEP em Ajax nativo instalada no input de endereço para converter o código postal da form na Rua e Bairro correspondente.
�️ Modelagem de Dados
O projeto conta com uma topologia de Models coesa no arquivo models.py enriquecida recentemente para um ecossistema gamificado completo:

ParticipanteRoleta: A Entidade pai, guardando todas as "rodadas" que a roleta gera, seus horários, e se foi ganho, perdido e qual foi o nome do participante ou se é um membro autenticado.
MembroClube: O CRM logado. Possui as regras de engajamento (CPF, Status, ClientID externo) e as Carteiras Virtuais (Saldo de Pontos/Giros, Nível Atual de Patente, e medidor de Experiência - XP).
PremioRoleta: O inventário do jogo. Permite cadastrar nome, tipo de prêmio, peso da probabilidade do sorteio e rigorosos Limites de estoque mensal/diário geolocalizados por cidade.
Missoes & Recompensas: Entidades que vinculam o cliente à tarefas externas, provendo bônus automatizado na carteira virtual e XP (Extratos detalhados de histórico de gamificação).
🔒 Proteções e Segurança (Rate Limits)
Sessions via OTP: Em vez de senhas complexas, os Sessões (request.session) do framework injetam um Cookie seguro no navegador apenas do momento que o código chega do n8n limitando qualquer ataque direto.
Cool-Dows (Rate Limiting de SMS): Usuários não podem floodar custos de API. A requisição verifica em sessão e trava novos envios de código por até 60 segundos. Tentativas de bypass recebem códigos HTTP 429 - Too Many Requests.
💻 Como Executar Localmente
1. Clonar e Iniciar o Ambiente
# Clone o repositório
git clone https://github.com/consulteplus/megaroleta.git

# Acesse a pasta
cd megaroleta

# Crie o ambiente virtual em Python
python -m venv .venv
Ative o ambiente:

Windows (cmd / powershell): .\.venv\Scripts\activate
Mac / Linux: source .venv/bin/activate
2. Instalação e Banco
# Instale os pacotes básicos
pip install django requests pillow python-dotenv
Suba o painel subjacente do framework recriando o mapa local:

python manage.py makemigrations
python manage.py migrate

# Configure um primeiro gerente do Django
python manage.py createsuperuser
3. Executar Servidor
python manage.py runserver
Vá para o navegador. A landing principal da engrenagem estará na URL http://127.0.0.1:8000/roleta. Para criar prêmios falsos no sistema de teste, acesse: http://127.0.0.1:8000/admin.

🚀 Desdobramentos e Deploy em Produção (Roadmap)
Para escalar usando servidores reais:

Migre os arquivos estáticos configurando o STATIC_ROOT para um bucket servido via Nginx.
Atualize do banco dev com o adaptador .env no settings.py para injetar o PostgreSQL.
Troque o servidor padrão com gunicorn megasorteio.wsgi.
Próximas Atividades Mapeadas (Future Proofing)
Refatoração Módulo (Design Pattern): Desdobrar o engessado arquivo de View Models em "Services" (HubsoftService, WebhookService).
Gamificação Avançada: Implementação de pontuações complexas a cada visita ou contrato renovado do ERP para turbinar a experiência da roleta diária (Mega Tokens).
Membro-Referral (Comissionamento Digital): O módulo MembroClube possuirá um código URL de convite para amigos que fornecerá giros grátis mútuos se os indicados conseguirem validar o número de telefone no Banco de Dados.
Desenvolvido de ponta a ponta com carinho para engajar leads reais e alavancar métricas do hub comercial. 🎰