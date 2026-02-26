from django.apps import AppConfig
import os
import sys


class ClientesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clientes'
    _scheduler_started = False

    def ready(self):
        """Configura o agendamento automático quando a aplicação estiver pronta"""
        # Não inicializar em comandos de gerenciamento (migrate, shell, etc)
        if 'manage.py' in sys.argv or 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
            
        # Evitar múltiplas inicializações
        if ClientesConfig._scheduler_started:
            return
            
        ClientesConfig._scheduler_started = True
        
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import atexit
        import logging
        import threading

        logger = logging.getLogger('clientes')

        def sincronizar():
            """Função que será executada periodicamente"""
            try:
                from django.core.management import call_command
                call_command('sincronizar_clientes')
                logger.info('Sincronização automática de clientes executada com sucesso')
            except Exception as e:
                logger.error(f'Erro na sincronização automática: {e}', exc_info=True)

        # Criar o scheduler em uma thread separada
        def start_scheduler():
            try:
                scheduler = BackgroundScheduler()
                
                # Agendar a sincronização a cada 2 horas, das 00:00 às 22:00
                # Horários: 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00
                scheduler.add_job(
                    sincronizar,
                    trigger=CronTrigger(hour='0,2,4,6,8,10,12,14,16,18,20,22', minute=0),
                    id='sincronizar_clientes',
                    name='Sincronizar clientes do banco externo (a cada 2h até 22h)',
                    replace_existing=True
                )

                # Iniciar o scheduler
                scheduler.start()
                logger.info('Agendador de sincronização de clientes iniciado (executa a cada 2 horas até 22:00)')

                # Registrar função para parar o scheduler quando a aplicação encerrar
                atexit.register(lambda: scheduler.shutdown())
            except Exception as e:
                logger.error(f'Erro ao iniciar scheduler: {e}', exc_info=True)

        # Iniciar o scheduler em uma thread separada
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
