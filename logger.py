# =====================================================================
# Módulo de Logging y Gestión de Eventos - Sistema Software FJ
# Descripción: Manejo seguro de archivos de texto para auditar eventos
# y capturar excepciones sin detener la ejecución de la aplicación.
#
# Se agregó el parámetro "mostrar"
# para que los eventos normales no llenen la consola del menú, y el log
# de errores ahora incluye la causa original de las excepciones encadenadas.
# =====================================================================

from datetime import datetime              # Fecha y hora de cada evento
from excepciones import SoftwareFJError    # Excepción base del sistema


def registrar_evento(log_type: str, mensaje: str, ruta_archivo: str = "logs.txt", mostrar: bool = False) -> bool:
    """
    Registra un evento o error en el archivo de logs del sistema.
    Usa bloques try/except/else/finally para garantizar la captura segura del fallo.
    """
    archivo = None   # Referencia al archivo (se cierra en finally)
    exito = False    # Indica si se pudo escribir
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")      # Momento del evento
    linea_log = f"[{timestamp}] [{log_type.upper()}]: {mensaje}\n"  # Línea a escribir

    try:
        # Abrir el archivo en modo append (agregar al final)
        archivo = open(ruta_archivo, "a", encoding="utf-8")
        archivo.write(linea_log)
    except IOError as err:
        # Si ocurre un error al escribir el archivo, se usa encadenamiento de excepciones
        print(f"Fallo crítico al escribir en el log: {err}")
        raise SoftwareFJError("No se pudo escribir en el archivo de auditoría.") from err
    else:
        # Se ejecuta únicamente si la apertura y escritura fueron exitosas
        exito = True
        if mostrar:  # Solo se imprime si se pide (ajuste de integración)
            print(f"Evento registrado correctamente: {log_type.upper()}")
    finally:
        # Garantiza el cierre del recurso independientemente de si hubo error o no
        if archivo and not archivo.closed:
            archivo.close()

    return exito


def procesar_operacion_segura(operacion_func, *args, **kwargs):
    """
    Función de envoltura para ejecutar operaciones complejas del sistema de forma segura.
    Captura excepciones personalizadas, las registra en el log y evita el colapso del programa.
    """
    try:
        resultado = operacion_func(*args, **kwargs)
        registrar_evento("INFO", f"Operación {operacion_func.__name__} ejecutada con éxito.")
        return resultado
    except SoftwareFJError as error:
        # Captura de excepciones personalizadas del dominio Software FJ
        causa = f" | causa: {type(error.__cause__).__name__}: {error.__cause__}" if error.__cause__ else ""
        registrar_evento("ERROR_NEGOCIO", f"{error}{causa}")
        print(f"Excepción controlada capturada: {error}")
        if error.__cause__:  # Ajuste de integración: también se muestra el error original
            print(f"  ↳ causado por {type(error.__cause__).__name__}: {error.__cause__}")
        return None
    except Exception as error_inesperado:
        # Encadenamiento de excepciones inesperadas
        registrar_evento("CRITICAL", f"Error insospechado: {error_inesperado}")
        print(f"Se ha producido un error inesperado en el sistema: {error_inesperado}")
        return None
