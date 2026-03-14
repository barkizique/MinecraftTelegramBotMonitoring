import asyncio
import psutil
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler
from mcstatus import JavaServer

print("Все импорты загружены успешно!")

# Конфигурация
TELEGRAM_BOT_TOKEN = "api token there"
CHAT_ID = # integer telegram bot id
MINECRAFT_SERVER_IP = "server ip there"
MINECRAFT_SERVER_PORT = 25565
CHECK_INTERVAL = 3600  # 1 час в секундах
TPS_THRESHOLD = 15

class MinecraftMonitor:
    def __init__(self):
        self.bot = None
        self.server = JavaServer.lookup(f"{MINECRAFT_SERVER_IP}:{MINECRAFT_SERVER_PORT}")
        
    async def get_server_status(self):
        """Получает статус сервера Minecraft"""
        try:
            status = await asyncio.to_thread(self.server.status)
            return {
                'online': True,
                'players': status.players.online,
                'player_list': status.players.sample if status.players.sample else [],
                'latency': status.latency
            }
        except Exception as e:
            return {'online': False, 'error': str(e)}
    
    def get_system_stats(self):
        """Получает статистику системы"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu': cpu_percent,
            'ram_used': memory.used / (1024 ** 3),  # GB
            'ram_total': memory.total / (1024 ** 3),  # GB
            'ram_percent': memory.percent
        }
    
    def estimate_tps(self, latency):
        """Оценка TPS на основе задержки (примерная)"""
        # Это упрощенная оценка, для точного TPS нужен плагин на сервере
        if latency < 50:
            return 20.0
        elif latency < 100:
            return 19.0
        elif latency < 200:
            return 17.0
        else:
            return max(10.0, 20.0 - (latency / 50))

    
    async def format_monitoring_message(self, server_status, system_stats, tps):
        """Форматирует сообщение мониторинга"""
        message = "🎮 <b>Мониторинг сервера Minecraft</b>\n\n"
        
        # TPS
        tps_emoji = "🟢" if tps >= 18 else "🟡" if tps >= 15 else "🔴"
        message += f"{tps_emoji} <b>TPS:</b> {tps:.1f}\n\n"
        
        # Игроки
        if server_status['players'] > 0:
            message += f"👥 <b>Игроки онлайн:</b> {server_status['players']}\n"
            if server_status['player_list']:
                players = [p.name for p in server_status['player_list']]
                message += f"   • {', '.join(players)}\n"
        else:
            message += "👥 <b>Игроки:</b> Нет игроков\n"
        
        message += "\n"
        
        # Оперативная память
        message += f"💾 <b>Оперативная память:</b>\n"
        message += f"   • Использовано: {system_stats['ram_used']:.2f} GB / {system_stats['ram_total']:.2f} GB\n"
        message += f"   • Загрузка: {system_stats['ram_percent']:.1f}%\n\n"
        
        # Процессор
        cpu_emoji = "🟢" if system_stats['cpu'] < 70 else "🟡" if system_stats['cpu'] < 90 else "🔴"
        message += f"{cpu_emoji} <b>Загрузка процессора:</b> {system_stats['cpu']:.1f}%\n\n"
        
        message += f"🕐 <i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>"
        
        return message
    
    async def send_low_tps_alert(self, tps, players):
        """Отправляет уведомление о низком TPS"""
        message = f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        message += f"TPS упал ниже порога: <b>{tps:.1f}</b>\n"
        message += f"Игроков онлайн: {players}"
        
        await self.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='HTML'
        )

    
    async def monitoring_loop(self):
        """Основной цикл мониторинга"""
        while True:
            try:
                # Получаем статус сервера
                server_status = await self.get_server_status()
                
                if not server_status['online']:
                    print(f"Сервер недоступен: {server_status.get('error', 'Unknown error')}")
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                # Если нет игроков, пропускаем отправку
                if server_status['players'] == 0:
                    print("Нет игроков онлайн, пропускаем отправку")
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                # Получаем системную статистику
                system_stats = self.get_system_stats()
                
                # Оцениваем TPS
                tps = self.estimate_tps(server_status['latency'])
                
                # Формируем и отправляем сообщение
                message = await self.format_monitoring_message(server_status, system_stats, tps)
                await self.bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode='HTML'
                )
                
                # Проверяем TPS и отправляем алерт если нужно
                if tps < TPS_THRESHOLD:
                    await self.send_low_tps_alert(tps, server_status['players'])
                
                print(f"Отчет отправлен. TPS: {tps:.1f}, Игроков: {server_status['players']}")
                
            except Exception as e:
                print(f"Ошибка в цикле мониторинга: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
    
    async def start_command(self, update, context):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "🎮 Бот мониторинга Minecraft сервера запущен!\n\n"
            "Команды:\n"
            "/status - Текущий статус сервера\n"
            "/start - Показать это сообщение"
        )

    
    async def status_command(self, update, context):
        """Обработчик команды /status"""
        try:
            server_status = await self.get_server_status()
            
            if not server_status['online']:
                await update.message.reply_text(
                    f"❌ Сервер недоступен\n{server_status.get('error', '')}",
                    parse_mode='HTML'
                )
                return
            
            system_stats = self.get_system_stats()
            tps = self.estimate_tps(server_status['latency'])
            message = await self.format_monitoring_message(server_status, system_stats, tps)
            
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    
    async def run(self):
        """Запуск бота"""
        # Создаем приложение
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = app.bot
        
        # Регистрируем команды
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        
        # Запускаем бота
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        print("Бот запущен!")
        
        # Запускаем цикл мониторинга
        await self.monitoring_loop()

async def main():
    print("=== Запуск бота мониторинга ===")
    print(f"Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"Chat ID: {CHAT_ID}")
    print(f"Server: {MINECRAFT_SERVER_IP}:{MINECRAFT_SERVER_PORT}")
    print("================================")
    
    monitor = MinecraftMonitor()
    await monitor.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
