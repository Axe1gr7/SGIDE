import os
import subprocess
from datetime import datetime
from flask import current_app
from docxtpl import DocxTemplate
from app.models import Alumno, Expediente
from app.services.file_manager import generar_ruta_relativa_expediente


def generar_documento_word(alumno_id, tipo_modulo, template_name=None):
    """
    Generates a Word document from a template for a specific student and module.
    tipo_modulo: 'p' (practicas), 's' (servicio), 'v' (vinculacion)
    Returns: filepath of the generated document.
    """
    alumno = Alumno.query.get_or_404(alumno_id)
    expediente = Expediente.query.filter_by(
        alumno_id=alumno_id,
        tipo_modulo=tipo_modulo,
        is_deleted=False
    ).first_or_404()

    # Map module type to default template name (fallback)
    default_template_map = {
        'p': 'plantilla_practicas.docx',
        's': 'plantilla_servicio.docx',
        'v': 'plantilla_vinculacion.docx'
    }

    # Determine the template to use. If a specific template_name is provided, use it; otherwise fallback to default mapping.
    if not template_name:
        template_name = default_template_map.get(tipo_modulo)
    if not template_name:
        raise ValueError(f'Tipo de módulo inválido y no se proporcionó plantilla: {tipo_modulo}')

    template_path = os.path.join(current_app.config['TEMPLATES_WORD_FOLDER'], template_name)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f'Plantilla no encontrada: {template_name}')

    # Render template
    doc = DocxTemplate(template_path)

    modulo_nombres = {'p': 'Prácticas Profesionales', 's': 'Servicio Social', 'v': 'Vinculación'}

    dependencia = expediente.dependencia
    carrera_nombre = alumno.carrera.nombre if alumno.carrera else ''

    context = {
        'nombre': alumno.nombre or '',
        'matricula': alumno.matricula or '',
        'carrera': carrera_nombre,
        'generacion': alumno.generacion_completa,
        'estatus': alumno.estatus or '',
        'sector': expediente.sector or '',
        'dependencia': dependencia.nombre if dependencia else '',
        'dependencia_nombre': dependencia.nombre if dependencia else '',
        'dependencia_direccion': getattr(dependencia, 'domicilio', '') if dependencia else '',
        'dependencia_contacto': getattr(dependencia, 'contacto', '') if dependencia else '',
        'dependencia_sector': getattr(dependencia, 'sector', '') if dependencia else '',
        'expediente_base': alumno.expediente_base or '',
        'clave_expediente': expediente.clave_expediente,
        'tipo_modulo': modulo_nombres.get(tipo_modulo, tipo_modulo),
        'fecha': datetime.now().strftime('%d/%m/%Y'),
        'anio': datetime.now().year,
    }

    doc.render(context)

    # Save generated file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{expediente.clave_expediente}_{timestamp}.docx"

    ruta_relativa = generar_ruta_relativa_expediente(expediente)
    ruta_absoluta_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], ruta_relativa)
    os.makedirs(ruta_absoluta_dir, exist_ok=True)

    output_path = os.path.join(ruta_absoluta_dir, filename)
    doc.save(output_path)

    return output_path, filename


def generar_documento_pdf(alumno_id, tipo_modulo, template_name=None):
    """Renderiza una plantilla Word con datos reales y la convierte a PDF."""
    docx_path, docx_filename = generar_documento_word(
        alumno_id, tipo_modulo, template_name=template_name
    )
    output_dir = os.path.dirname(docx_path)
    pdf_filename = f'{os.path.splitext(docx_filename)[0]}.pdf'
    pdf_path = os.path.join(output_dir, pdf_filename)

    try:
        subprocess.run(
            [
                'libreoffice', '--headless', '--convert-to', 'pdf',
                '--outdir', output_dir, docx_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise RuntimeError('El conversor LibreOffice no está instalado en el servidor.') from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or '').strip()
        raise RuntimeError(f'No se pudo convertir el formato a PDF: {detail}') from exc

    if not os.path.exists(pdf_path):
        raise RuntimeError('LibreOffice no generó el archivo PDF esperado.')

    return pdf_path, pdf_filename


def listar_plantillas_word():
    """Retorna una lista de diccionarios con clave y nombre para las plantillas en la carpeta de plantillas Word."""
    carpeta = current_app.config.get('TEMPLATES_WORD_FOLDER')
    if not carpeta or not os.path.isdir(carpeta):
        return []
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith('.docx')]
    # Ordenar alfabéticamente
    archivos.sort()
    return [{'key': os.path.splitext(f)[0], 'display_name': f.replace('_', ' ').replace('.docx', '')} for f in archivos]
