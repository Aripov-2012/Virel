import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> bool:
    """Отправляет SMS через настроенный бэкенд."""
    backend = getattr(settings, 'SMS_BACKEND', 'console')

    if backend == 'console':
        return _send_console(phone, message)
    elif backend == 'twilio':
        return _send_twilio(phone, message)
    elif backend == 'custom':
        return _send_custom(phone, message)

    logger.error(f"Неизвестный SMS бэкенд: {backend}")
    return False


def _send_console(phone: str, message: str) -> bool:
    """Выводит код в консоль (для разработки)."""
    print(f"\n{'='*50}")
    print(f"SMS → {phone}")
    print(f"Текст: {message}")
    print(f"{'='*50}\n")
    logger.info(f"SMS to {phone}: {message}")
    return True


def _send_twilio(phone: str, message: str) -> bool:
    """Отправка через Twilio (нужен pip install twilio)."""
    try:
        from twilio.rest import Client
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        from_number = settings.TWILIO_FROM_NUMBER
        client = Client(account_sid, auth_token)
        client.messages.create(body=message, from_=from_number, to=phone)
        return True
    except Exception as e:
        logger.error(f"Twilio error: {e}")
        return False


def _send_custom(phone: str, message: str) -> bool:
    """Заготовка для вашего SMS-провайдера.
    Реализуйте здесь вызов API вашего провайдера.
    """
    logger.warning("Custom SMS backend не реализован. Добавьте код в blog/sms.py")
    return False
