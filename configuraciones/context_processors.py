from django.conf import settings

def global_config(request):
    """
    Context processor to make global variables available in all templates.
    """
    return {
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', '573014717412'),
        'paypal_client_id': getattr(settings, 'PAYPAL_CLIENT_ID', 'sb'),
        'paypal_currency': getattr(settings, 'PAYPAL_CURRENCY', 'USD'),
    }
