import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from flask import current_app
from docxtpl import DocxTemplate
from lxml import etree
from app.extensions import db
from app.models import Alumno, Dependencia, Expediente, Practica
from app.services.file_manager import generar_ruta_relativa_expediente

FORMATO_ACREDITACION_PP_FILENAME = 'Formato Constancia de Acreditacion PP 2025.docx'
_WORD_NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_WORD_NAMESPACES = {'w': _WORD_NAMESPACE}


def _obtener_ruta_plantilla(template_name):
    """Busca plantillas administrables y el machote institucional de PP."""
    template_path = os.path.join(current_app.config['TEMPLATES_WORD_FOLDER'], template_name)
    if os.path.exists(template_path):
        return template_path

    if template_name == FORMATO_ACREDITACION_PP_FILENAME:
        project_root = os.path.dirname(current_app.root_path)
        return os.path.join(project_root, 'machotes', template_name)

    return template_path


def _actualizar_campos_combinacion(docx_path, valores):
    """Actualiza los resultados visibles de campos MERGEFIELD en un documento Word."""
    with zipfile.ZipFile(docx_path, 'r') as source:
        try:
            document_xml = source.read('word/document.xml')
        except KeyError:
            return

        root = etree.fromstring(document_xml)
        field_type = f'{{{_WORD_NAMESPACE}}}fldCharType'
        for paragraph in root.xpath('.//w:p', namespaces=_WORD_NAMESPACES):
            field_name = None
            collecting_instruction = False
            collecting_result = False
            result_nodes = []

            for run in paragraph.xpath('.//w:r', namespaces=_WORD_NAMESPACES):
                field_chars = run.xpath('.//w:fldChar', namespaces=_WORD_NAMESPACES)
                if any(char.get(field_type) == 'begin' for char in field_chars):
                    field_name = ''
                    collecting_instruction = True
                    collecting_result = False
                    result_nodes = []
                    continue

                if collecting_instruction:
                    field_name += ''.join(
                        node.text or ''
                        for node in run.xpath('.//w:instrText', namespaces=_WORD_NAMESPACES)
                    )
                    if any(char.get(field_type) == 'separate' for char in field_chars):
                        collecting_instruction = False
                        collecting_result = True
                    continue

                if collecting_result:
                    if any(char.get(field_type) == 'end' for char in field_chars):
                        match = re.search(r'MERGEFIELD\s+([^\s\\]+)', field_name or '')
                        if match and match.group(1) in valores and result_nodes:
                            result_nodes[0].text = str(valores[match.group(1)] or '')
                            for node in result_nodes[1:]:
                                node.text = ''
                        field_name = None
                        collecting_result = False
                        result_nodes = []
                    else:
                        result_nodes.extend(run.xpath('.//w:t', namespaces=_WORD_NAMESPACES))

        temporary = tempfile.NamedTemporaryFile(
            suffix='.docx', dir=os.path.dirname(docx_path), delete=False
        )
        temporary.close()
        try:
            with zipfile.ZipFile(temporary.name, 'w') as destination:
                for member in source.infolist():
                    content = etree.tostring(
                        root, xml_declaration=True, encoding='UTF-8', standalone=True
                    ) if member.filename == 'word/document.xml' else source.read(member.filename)
                    destination.writestr(member, content)
            os.replace(temporary.name, docx_path)
        finally:
            if os.path.exists(temporary.name):
                os.remove(temporary.name)


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
        'p': FORMATO_ACREDITACION_PP_FILENAME,
        's': 'plantilla_servicio.docx',
        'v': 'plantilla_vinculacion.docx'
    }

    # Determine the template to use. If a specific template_name is provided, use it; otherwise fallback to default mapping.
    if not template_name:
        template_name = default_template_map.get(tipo_modulo)
    if not template_name:
        raise ValueError(f'Tipo de módulo inválido y no se proporcionó plantilla: {tipo_modulo}')

    template_path = _obtener_ruta_plantilla(template_name)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f'Plantilla no encontrada: {template_name}')

    # Render template
    doc = DocxTemplate(template_path)

    modulo_nombres = {'p': 'Prácticas Profesionales', 's': 'Servicio Social', 'v': 'Vinculación'}

    practica = None
    dependencia = expediente.dependencia
    if tipo_modulo == 'p':
        practica = Practica.query.filter_by(
            alumno_id=alumno_id, is_deleted=False
        ).order_by(Practica.id.desc()).first()
        if practica and practica.empresa:
            dependencia = Dependencia.query.filter(
                db.func.lower(Dependencia.nombre) == practica.empresa.strip().lower(),
                Dependencia.is_deleted == False,
            ).first() or dependencia
    carrera_nombre = alumno.carrera.nombre if alumno.carrera else ''

    MESES = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
        7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    now = datetime.now()
    mes_nombre = MESES.get(now.month, '')
    fecha_larga = f"{now.day} de {mes_nombre} de {now.year}"
    fecha_larga_upper = f"{now.day} DE {mes_nombre.upper()} DE {now.year}"

    def formatear_fecha_larga(valor):
        if not valor:
            return ''
        return f'{valor.day} de {MESES[valor.month]} de {valor.year}'

    fecha_inicio_practicas = formatear_fecha_larga(practica.f_inicio) if practica else ''
    fecha_fin_practicas = formatear_fecha_larga(practica.f_i_final) if practica else ''

    if practica:
        nombre_practica = practica.nombre or ''
        nombre_minusculas_practica = practica.nombre_minusculas or ''
        carrera_practica = practica.carrera or ''
        matricula_practica = practica.matricula or ''
        empresa_practica = practica.empresa or ''
    else:
        nombre_practica = alumno.nombre or ''
        nombre_minusculas_practica = (alumno.nombre or '').title()
        carrera_practica = carrera_nombre
        matricula_practica = alumno.matricula or ''
        empresa_practica = dependencia.nombre if dependencia else ''

    context = {
        'nombre': nombre_minusculas_practica,
        'NOMBRE': nombre_practica,
        'matricula': matricula_practica,
        'MATRICULA': matricula_practica,
        'carrera': carrera_practica,
        'CARRERA': carrera_practica,
        'generacion': alumno.generacion_completa,
        'GENERACION': alumno.generacion_completa,
        'estatus': alumno.estatus or '',
        'ESTATUS': (alumno.estatus or '').upper(),
        'sector': expediente.sector or '',
        'SECTOR': (expediente.sector or '').upper(),
        'dependencia': dependencia.nombre if dependencia else '',
        'DEPENDENCIA': (dependencia.nombre if dependencia else '').upper(),
        'dependencia_nombre': dependencia.nombre if dependencia else '',
        'dependencia_direccion': getattr(dependencia, 'domicilio', '') if dependencia else '',
        'dependencia_contacto': getattr(dependencia, 'contacto', '') if dependencia else '',
        'dependencia_sector': getattr(dependencia, 'sector', '') if dependencia else '',
        'expediente_base': alumno.expediente_base or '',
        'clave_expediente': expediente.clave_expediente,
        'CLAVE_EXPEDIENTE': expediente.clave_expediente,
        'tipo_modulo': modulo_nombres.get(tipo_modulo, tipo_modulo),
        'fecha': now.strftime('%d/%m/%Y'),
        'FECHA': fecha_larga,
        'FECHA_UPPER': fecha_larga_upper,
        'dia': now.day,
        'mes': mes_nombre,
        'MES': mes_nombre.upper(),
        'anio': now.year,
        'ANIO': now.year,
        'NCONSTANCIA': practica.no_constancia if practica else '',
        'FINICIO': fecha_inicio_practicas,
        'FFIN': fecha_fin_practicas,
        'EMPRESA': empresa_practica,
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

    if tipo_modulo == 'p':
        turno = practica.turno if practica else ''
        consecutivo = practica.consecutivo if practica else ''
        empresa = practica.empresa if practica and practica.empresa else (dependencia.nombre if dependencia else '')
        _actualizar_campos_combinacion(output_path, {
            'TURNO': turno,
            'CONSECUTIVO': practica.no_registro if practica else consecutivo,
            'NOMBRE_2': nombre_practica,
            'MATRÍCULA': matricula_practica,
            'CARRERA': carrera_practica,
            'EMPRESA': empresa_practica,
            'FINICIO': fecha_inicio_practicas,
            'FFIN': fecha_fin_practicas,
        })

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
