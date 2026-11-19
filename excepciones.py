# =====================================================================
# Módulo de Excepciones Personalizadas - Sistema Software FJ
# Descripción: Jerarquía de clases de excepción para controlar fallos
# en clientes, servicios, reservas y cálculos del sistema.
# =====================================================================

class SoftwareFJError(Exception):
    """Clase base abstracta para todas las excepciones del sistema Software FJ."""
    def __init__(self, mensaje: str, codigo_error: int = 500):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_error = codigo_error

    def __str__(self):
        return f"[ERROR {self.codigo_error}]: {self.mensaje}"


class ClienteInvalidoError(SoftwareFJError):
    """Se dispara cuando los datos del cliente no cumplen con las validaciones."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=401)


class ServicioNoDisponibleError(SoftwareFJError):
    """Se dispara cuando un servicio solicitado no se encuentra activo o no existe."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=404)


class ReservaInvalidaError(SoftwareFJError):
    """Se dispara cuando la duración, estado o parámetros de una reserva son incorrectos."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=400)


class CalculoInconsistenteError(SoftwareFJError):
    """Se dispara ante inconsistencias numéricas en costos, descuentos o impuestos."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=422)


# =====================================================================
# Excepciones adicionales usadas por el menú y la simulación
# Completan los casos que pide el enunciado: datos inválidos, parámetros
# faltantes, servicios mal creados y operaciones no permitidas.
# Siguen el mismo formato de las anteriores (mensaje + código de error).
# =====================================================================

class DatoInvalidoError(SoftwareFJError):
    """Se dispara cuando un dato tiene formato o valor incorrecto (correo, documento, cantidad...)."""
    def __init__(self, mensaje: str, campo: str = None):
        super().__init__(mensaje, codigo_error=406)  # 406: dato no aceptable
        self.campo = campo  # Nombre del campo que falló (útil para depurar)


class ParametroFaltanteError(SoftwareFJError):
    """Se dispara cuando falta un parámetro obligatorio para crear un objeto u operar."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=412)  # 412: falta una condición previa


class ServicioInvalidoError(SoftwareFJError):
    """Se dispara cuando un servicio no se puede crear (tarifa negativa, tipo inexistente...)."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=409)  # 409: conflicto con las reglas del servicio


class OperacionNoPermitidaError(SoftwareFJError):
    """Se dispara cuando se intenta una operación que el estado actual no permite."""
    def __init__(self, mensaje: str):
        super().__init__(mensaje, codigo_error=403)  # 403: operación prohibida
