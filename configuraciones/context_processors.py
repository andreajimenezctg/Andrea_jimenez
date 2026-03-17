from django.conf import settings

def whatsapp_config(request):
    """
    Context processor to make the WhatsApp number available in all templates.
    """
    return {
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', '573014717412')
    }
