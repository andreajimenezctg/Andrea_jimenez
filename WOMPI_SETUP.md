# Configuración de Pago Wompi (Producción Empresarial)

## Flujo implementado

1. **Checkout**: Al cargar la página de pago se genera una referencia única y se guarda en `TransaccionWompiPendiente` para vincular con el cliente.
2. **Widget Wompi**: El usuario paga con PSE, tarjeta u otro método de Wompi.
3. **Webhook** (principal): Wompi envía `transaction.updated` a tu URL. Si el estado es `APPROVED`, se crea la venta, se vacía el carrito y se envía el correo con la factura.
4. **Redirect** (wompi_exito): El usuario vuelve a tu sitio. Si el webhook ya procesó, se le muestra la confirmación. Si no, se verifica con la API de Wompi y se crea la venta.

## Configuración obligatoria para producción

### 1. Llaves de Wompi

En el [Dashboard de Comercios Wompi](https://comercios.wompi.co/):

- **Llave pública** → `WOMPI_PUBLIC_KEY` en `settings.py` o variable de entorno
- **Secreto de integridad** (Widget) → `WOMPI_INTEGRITY_SECRET`
- **Secreto de eventos** (Webhooks) → `WOMPI_EVENTS_SECRET`  
  Ubicación: Mi cuenta > Secretos para integración técnica

### 2. URL del webhook

Configura en el Dashboard de Wompi la URL de eventos:

```
https://tudominio.com/wompi/webhook/
```

Para pruebas locales con ngrok:

```
ngrok http 8000
# Usar: https://abc123.ngrok.io/wompi/webhook/
```

### 3. Variables de entorno recomendadas

```bash
# Producción - usar variables de entorno
export WOMPI_PUBLIC_KEY="pub_prod_xxx"
export WOMPI_INTEGRITY_SECRET="prod_integrity_xxx"
export WOMPI_EVENTS_SECRET="prod_events_xxx"
```

En `settings.py`:

```python
WOMPI_PUBLIC_KEY = os.environ.get('WOMPI_PUBLIC_KEY', 'pub_test_...')
WOMPI_INTEGRITY_SECRET = os.environ.get('WOMPI_INTEGRITY_SECRET', '...')
WOMPI_EVENTS_SECRET = os.environ.get('WOMPI_EVENTS_SECRET', '...')
```

### 4. HTTPS

El webhook debe ser accesible por HTTPS. En local puedes usar ngrok o un túnel similar.
