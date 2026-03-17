import os
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from reportlab.lib.utils import ImageReader
from django.conf import settings
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def numero_a_letras(numero):
    """
    Convierte un número a su representación en palabras (Español).
    Implementación simplificada pero robusta para facturación.
    """
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    diez_a_diecinueve = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    veinte_a_veintinueve = ["VEINTE", "VEINTIUNO", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def convertir_grupo(n):
        if n == 0: return ""
        if n == 100: return "CIEN"
        
        resultado = ""
        c = n // 100
        d = (n % 100) // 10
        u = n % 10
        
        if c > 0: resultado += centenas[c] + " "
        
        if d == 1:
            resultado += diez_a_diecinueve[u]
        elif d == 2:
            if u == 0: resultado += "VEINTE"
            else: resultado += veinte_a_veintinueve[u]
        elif d > 2:
            resultado += decenas[d]
            if u > 0: resultado += " Y " + unidades[u]
        else:
            resultado += unidades[u]
        
        return resultado.strip()

    if numero == 0: return "CERO"
    
    entero = int(numero)
    millones = entero // 1000000
    miles = (entero % 1000000) // 1000
    unidades_resto = entero % 1000
    
    palabras = ""
    if millones > 0:
        if millones == 1: palabras += "UN MILLON "
        else: palabras += convertir_grupo(millones) + " MILLONES "
        
    if miles > 0:
        if miles == 1: palabras += "MIL "
        else: palabras += convertir_grupo(miles) + " MIL "
        
    if unidades_resto > 0:
        palabras += convertir_grupo(unidades_resto)
        
    return palabras.strip()

def generate_invoice_pdf(venta, buffer=None):
    if buffer is None:
        buffer = BytesIO()
    
    # Márgenes reducidos para diseño de grilla
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12*mm,
        leftMargin=12*mm,
        topMargin=15*mm,
        bottomMargin=35*mm,
        title=f"FACTURA DE VENTA #{venta.id}"
    )
    
    # Colores de marca
    color_primario = colors.HexColor("#000000")
    color_acento = colors.HexColor("#ff7a9c")
    color_fondo_suave = colors.HexColor("#fdf9f4")
    color_border = colors.HexColor("#dddddd")
    
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. ENCABEZADO ELITE (Grilla de 2 columnas)
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpg')
    logo = None
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=25*mm, height=25*mm)
    
    brand_style = ParagraphStyle(
        name='BrandTitle',
        parent=styles['Normal'],
        fontSize=20,
        leading=24,
        fontName='Helvetica-Bold',
        textColor=color_primario,
    )
    
    subtitle_style = ParagraphStyle(
        name='Subtitle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=color_acento,
        textTransform='uppercase'
    )

    brand_title = Paragraph("ANDREA JIMÉNEZ", brand_style)
    brand_subtitle = Paragraph("ALTA COSTURA COLOMBIANA", subtitle_style)
    
    # Cuadro de Resumen (Derecha)
    # Generamos un código de barras para la venta
    COD128 = barcode.get_barcode_class('code128')
    rv = BytesIO()
    code = COD128(f"{venta.id:06d}", writer=ImageWriter())
    code.write(rv, options={"module_height": 10.0, "font_size": 8, "text_distance": 3.0, "quiet_zone": 5.0})
    rv.seek(0)
    # IMPORTANTE: Para ReportLab.platypus.Image, pasamos el objeto BytesIO directamente
    invoice_barcode_img = Image(rv, width=35*mm, height=12*mm)
    
    summary_data = [
        [Paragraph("<font color='white' size=7>VENTA N°</font>", styles['Normal'])],
        [Paragraph(f"<font color='white' size=20><b>{str(venta.id).zfill(6)}</b></font>", styles['Normal'])],
        [invoice_barcode_img],
        [Paragraph(f"<font color='#ff7a9c' size=9><b>{venta.fecha_venta.strftime('%b %d, %Y').upper()}</b></font>", styles['Normal'])]
    ]
    summary_table = Table(summary_data, colWidths=[60*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), color_primario),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,3), (0,3), 3, color_acento),
    ]))
    
    left_cell = []
    if logo:
        left_cell.append(logo)
    left_cell.extend([brand_title, brand_subtitle])
    
    right_cell = [summary_table]
    
    header_table = Table([[left_cell, right_cell]], colWidths=[120*mm, 66*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10*mm))
    
    # 2. GRILLA DE INFORMACIÓN (Grid style)
    label_style = ParagraphStyle(name='Label', fontSize=7, textColor=color_acento, fontName='Helvetica-Bold', textTransform='uppercase', letterSpacing=1)
    value_style = ParagraphStyle(name='Value', fontSize=10, textColor=color_primario, fontName='Helvetica-Bold')
    
    def grid_cell(label, value, highlight=False):
        cell_content = [Paragraph(label, label_style), Spacer(1, 2*mm), Paragraph(str(value).upper(), value_style)]
        return cell_content

    client_name = venta.cliente.user.get_full_name() or venta.cliente.user.username
    
    info_data = [
        [grid_cell("CLIENTE", client_name), grid_cell("MÉTODO DE PAGO", venta.pago.metodo if venta.pago else "PSE")],
        [grid_cell("DIRECCIÓN", venta.cliente.direccion or "CARTAGENA, COLOMBIA"), grid_cell("ESTADO", venta.pago.estado if venta.pago else "APROBADO")],
        [grid_cell("NIT / CC", "900.123.456-1"), grid_cell("CONTACTO", f"{venta.cliente.telefono or 'N/A'} | {venta.cliente.user.email}")]
    ]
    
    info_grid = Table(info_data, colWidths=[93*mm, 93*mm])
    info_grid.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BACKGROUND', (0,0), (0,0), color_fondo_suave), # Highlight Cliente
    ]))
    elements.append(info_grid)
    elements.append(Spacer(1, 10*mm))
    
    # 3. TABLA DE PRODUCTOS
    data_items = [["CÓDIGO", "PRODUCTO", "CÓDIGO DE BARRAS", "CANT.", "PRECIO", "TOTAL"]]
    detalles = venta.detalles.all()
    for d in detalles:
        # Intentamos obtener la imagen del código de barras si existe
        barcode_flowable = ""
        if hasattr(d.prenda, 'barcode_image') and d.prenda.barcode_image:
            barcode_path = os.path.join(settings.MEDIA_ROOT, d.prenda.barcode_image.name)
            if os.path.exists(barcode_path):
                # Usamos el path directamente para mayor compatibilidad
                try:
                    barcode_flowable = Image(barcode_path, width=30*mm, height=10*mm)
                except Exception:
                    barcode_flowable = "ERROR IMG"
        
        data_items.append([
            getattr(d.prenda, 'codigo_barras', None) or f"AJ-{d.prenda.id:04d}",
            Paragraph(f"<b>{d.prenda.nombre.upper()}</b>", styles['Normal']),
            barcode_flowable,
            str(d.cantidad),
            f"${d.precio_unitario:,.0f}",
            f"${(d.cantidad * d.precio_unitario):,.0f}"
        ])
    
    table_items = Table(data_items, colWidths=[25*mm, 66*mm, 30*mm, 15*mm, 25*mm, 25*mm])
    table_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primario),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (2,1), (5,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(table_items)
    elements.append(Spacer(1, 10*mm))
    
    # 4. TOTALES Y VALOR EN LETRAS
    total_letras = numero_a_letras(venta.total or 0)
    
    footer_left = [
        Paragraph("VALOR EN LETRAS", label_style),
        Spacer(1, 2*mm),
        Paragraph(f"<b>{total_letras} PESOS M/CTE</b>", styles['Normal'])
    ]
    
    total_valor = venta.total or 0
    footer_right_table = Table([
        [Paragraph("TOTAL BRUTO", styles['Normal']), f"${total_valor:,.0f}"],
        [Paragraph("IVA (0%)", styles['Normal']), "$0"],
        [Paragraph("<font color='white'><b>TOTAL A PAGAR</b></font>", styles['Normal']), Paragraph(f"<font color='white'><b>${total_valor:,.0f}</b></font>", styles['Normal'])]
    ], colWidths=[40*mm, 35*mm], rowHeights=[8*mm, 8*mm, 12*mm])
    
    footer_right_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BACKGROUND', (0,2), (0,2), color_primario),
        ('BACKGROUND', (1,2), (1,2), color_primario),
        ('TEXTCOLOR', (0,2), (1,2), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBEFORE', (1,2), (1,2), 4, color_acento),
        ('FONTNAME', (0,2), (1,2), 'Helvetica-Bold'),
    ]))
    
    total_section = Table([[footer_left, [footer_right_table]]], colWidths=[111*mm, 75*mm])
    total_section.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(total_section)

    def on_page(canvas, doc):
        canvas.saveState()
        # Footer decoration
        canvas.setFillColor(color_fondo_suave)
        canvas.rect(0, 0, 210*mm, 25*mm, stroke=0, fill=1)
        canvas.setFillColor(color_primario)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(15*mm, 15*mm, "ANDREA JIMÉNEZ OFFICIAL")
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15*mm, 11*mm, "CARTAGENA, BOLÍVAR | COLOMBIA")
        
        # QR Code in footer using local qrcode library for faster generation
        try:
            invoice_url = f"{settings.SITE_URL}/factura/{venta.id}/"
            qr = qrcode.QRCode(version=1, box_size=2, border=1)
            qr.add_data(invoice_url)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white")
            qr_buffer = BytesIO()
            img_qr.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            qr_img_reader = ImageReader(qr_buffer)
            canvas.drawImage(qr_img_reader, 175*mm, 3*mm, width=20*mm, height=20*mm, preserveAspectRatio=True, mask='auto')
            canvas.setFont("Helvetica", 6)
            canvas.setFillColor(color_primario)
            canvas.drawCentredString(185*mm, 2*mm, "ESCANEAME")
        except Exception as e:
            print(f"QR PDF no disponible: {e}")

        canvas.drawRightString(195*mm, 7*mm, f"Página {doc.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer
