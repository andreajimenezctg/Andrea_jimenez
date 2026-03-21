from django.conf import settings

def global_config(request):
    """
    Context processor to make global variables available in all templates.
    """
    es_cliente = False
    if request.user.is_authenticated:
        es_cliente = request.user.groups.filter(name='Cliente').exists()
        
    return {
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', '573014717412'),
        'es_cliente': es_cliente,
    }
