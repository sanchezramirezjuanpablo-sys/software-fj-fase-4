"""
reserva.py
----------
Contiene dos clases:
    - Reserva: une un cliente, un servicio y una duración, y controla
      su ciclo de vida con estados:

    PENDIENTE --confirmar()--> CONFIRMADA --procesar()--> PROCESADA
        |                          |
        +------cancelar()----------+--> CANCELADA

    - SistemaGestion: guarda en listas internas los clientes, servicios y
      reservas (sin base de datos) y ofrece todas las operaciones del negocio.

Aquí se usan las tres variantes de bloques de excepciones que pide la guía:
    try/except/else     -> confirmar()
    try/except/finally  -> cancelar()
    try/except/else/finally + encadenamiento (raise ... from ...) -> procesar()
"""

import traceback                                 # Detalle completo de errores inesperados

from cliente import Cliente                     # Para comprobar el tipo del cliente
from base import EntidadBase                     # Clase abstracta padre
from excepciones import (                       # Excepciones propias
    CalculoInconsistenteError,
    ClienteInvalidoError,
    DatoInvalidoError,
    OperacionNoPermitidaError,
    ParametroFaltanteError,
    ReservaInvalidaError,
    ServicioInvalidoError,
    ServicioNoDisponibleError,
    SoftwareFJError,
)
from logger import registrar_evento             # Registro de eventos
from servicios import (IVA, AlquilerEquipo, AsesoriaEspecializada,  # Servicios y utilidades
                       ReservaSala, Servicio, formato_pesos)  # Clase Servicio, IVA y formato de pesos


# Estados posibles de una reserva
PENDIENTE = "PENDIENTE"
CONFIRMADA = "CONFIRMADA"
PROCESADA = "PROCESADA"
CANCELADA = "CANCELADA"


class Reserva(EntidadBase):
    """Reserva de un servicio hecha por un cliente."""

    PREFIJO = "RES"  # Los IDs de reservas serán RES-0001, RES-0002...

    def __init__(self, cliente, servicio, duracion, **detalles):
        # El cliente debe ser un objeto Cliente de verdad
        if not isinstance(cliente, Cliente):
            raise ReservaInvalidaError(f"El cliente {cliente!r} no es válido")
        # El servicio debe ser cualquier subclase de Servicio (polimorfismo)
        if not isinstance(servicio, Servicio):
            raise ReservaInvalidaError(f"El servicio {servicio!r} no es válido")
        try:
            duracion = float(duracion)  # Aceptamos "3" o 3, pero no "tres"
        except (TypeError, ValueError) as error:
            # Encadenamiento: guardamos el error original de Python como causa
            raise ReservaInvalidaError(f"La duración {duracion!r} no es un número") from error
        try:
            servicio.validar_parametros(duracion, **detalles)  # Cada servicio valida a su manera
        except DatoInvalidoError as error:
            # Convertimos el error de dato en un error de reserva, conservando la causa
            raise ReservaInvalidaError(f"Los datos de la reserva no sirven para {servicio.nombre}") from error
        super().__init__()                # Asigna ID y fecha de creación
        self._cliente = cliente           # Quién reserva
        self._servicio = servicio         # Qué reserva
        self._duracion = duracion         # Cuánto tiempo
        self._detalles = detalles         # Datos extra: personas, cantidad...
        self._estado = PENDIENTE          # Toda reserva empieza pendiente
        self._costo_total = None          # Se conoce al procesar
        registrar_evento("INFO", f"Reserva {self.id} creada: {cliente.nombre} -> {servicio.nombre} ({duracion:g} {servicio.UNIDAD})")

    # ------------------------------------------------------------------
    # Propiedades de solo lectura
    # ------------------------------------------------------------------

    @property
    def cliente(self):
        return self._cliente  # Cliente de la reserva

    @property
    def servicio(self):
        return self._servicio  # Servicio reservado

    @property
    def estado(self):
        return self._estado  # Estado actual

    @property
    def costo_total(self):
        return self._costo_total  # None hasta que se procese

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def confirmar(self):
        """Aparta el servicio. Usa try/except/else."""
        if self._estado != PENDIENTE:  # Solo se confirma lo que está pendiente
            raise OperacionNoPermitidaError(f"No se puede 'confirmar' una reserva en estado {self._estado}")
        try:
            self._servicio.ocupar(**self._detalles)  # Puede lanzar ServicioNoDisponibleError
        except ServicioNoDisponibleError:
            # Registramos el fallo y dejamos que el error siga hacia arriba
            registrar_evento("ERROR", f"Reserva {self.id} no se pudo confirmar: servicio no disponible")
            raise
        else:
            # El bloque else solo corre si NO hubo excepción
            self._estado = CONFIRMADA
            registrar_evento("INFO", f"Reserva {self.id} CONFIRMADA")
        return self  # Permite encadenar: reserva.confirmar().procesar()

    def cancelar(self, motivo="sin motivo"):
        """Cancela la reserva y libera el servicio. Usa try/except/finally."""
        estado_anterior = self._estado  # Lo guardamos para el log
        try:
            if self._estado in (PROCESADA, CANCELADA):  # Ya no se puede cancelar
                raise OperacionNoPermitidaError(f"No se puede 'cancelar' una reserva en estado {self._estado}")
            if self._estado == CONFIRMADA:  # Si estaba confirmada, devolvemos lo apartado
                self._servicio.liberar(**self._detalles)
            self._estado = CANCELADA  # Nuevo estado
            registrar_evento("INFO", f"Reserva {self.id} CANCELADA ({motivo})")
        except OperacionNoPermitidaError:
            registrar_evento("ERROR", f"Intento de cancelar {self.id} en estado {self._estado}")
            raise  # Avisamos al que llamó
        finally:
            # finally corre SIEMPRE, haya error o no: dejamos rastro del intento
            registrar_evento("DEBUG", f"Intento de cancelación de {self.id}: {estado_anterior} -> {self._estado}")
        return self

    def procesar(self, impuesto=IVA, descuento=None):
        """
        Calcula el costo final y cierra la reserva.
        Usa try/except/else/finally y encadenamiento de excepciones.
        """
        if self._estado != CONFIRMADA:  # Solo se procesa lo confirmado
            raise OperacionNoPermitidaError(f"No se puede 'procesar' una reserva en estado {self._estado}")
        try:
            costo = self._servicio.calcular_costo(  # Polimorfismo: cada servicio calcula distinto
                self._duracion, impuesto=impuesto, descuento=descuento, **self._detalles
            )
        except CalculoInconsistenteError:
            registrar_evento("ERROR", f"Cálculo inconsistente al procesar {self.id}")
            raise  # Ya es un error propio; lo dejamos subir tal cual
        except (DatoInvalidoError, ArithmeticError, TypeError) as error:
            # Cualquier otro problema de cálculo se convierte en CalculoInconsistenteError
            raise CalculoInconsistenteError(f"No se pudo procesar {self.id}: {error}") from error
        else:
            # Sin errores: guardamos el costo y cerramos la reserva
            self._costo_total = costo
            self._estado = PROCESADA
            registrar_evento("INFO", f"Reserva {self.id} PROCESADA por {formato_pesos(costo)}")
        finally:
            # Siempre queda registro del intento, salga bien o mal
            registrar_evento("DEBUG", f"Intento de procesar {self.id} terminó en estado {self._estado}")
        return self

    # ------------------------------------------------------------------
    # Métodos obligatorios de EntidadBase
    # ------------------------------------------------------------------

    def describir(self):
        costo = formato_pesos(self._costo_total) if self._costo_total is not None else "por calcular"
        extra = ", ".join(f"{k}={v}" for k, v in self._detalles.items())  # Ej.: "personas=8"
        extra = f" ({extra})" if extra else ""  # Solo si hay detalles
        return (f"Reserva {self.id}: {self._cliente.nombre} -> {self._servicio.nombre} | "
                f"{self._duracion:g} {self._servicio.UNIDAD}(s){extra} | {self._estado} | {costo}")

    def validar(self):
        self._cliente.validar()  # El cliente sigue siendo válido
        self._servicio.validar_parametros(self._duracion, **self._detalles)  # Parámetros coherentes
        return True


# ======================================================================
# Gestor del sistema: listas internas y operaciones del negocio
# ======================================================================

# Tipos de servicio que el sistema sabe crear (nombre corto -> clase)
TIPOS_SERVICIO = {
    "sala": ReservaSala,
    "equipo": AlquilerEquipo,
    "asesoria": AsesoriaEspecializada,
}


class SistemaGestion:
    """Gestiona clientes, servicios y reservas de Software FJ en memoria."""

    def __init__(self):
        self._clientes = []     # Lista interna de clientes
        self._servicios = []    # Lista interna de servicios
        self._reservas = []     # Lista interna de reservas
        self._exitosas = 0      # Operaciones que salieron bien
        self._fallidas = 0      # Operaciones que fallaron (controladas)
        registrar_evento("INFO", "=== Sistema Software FJ iniciado ===")

    # ------------------------------------------------------------------
    # Red de seguridad: ninguna operación puede tumbar el programa
    # ------------------------------------------------------------------

    def ejecutar(self, numero, descripcion, operacion, *args, **kwargs):
        """Corre operacion(*args, **kwargs) de forma segura y muestra el resultado."""
        print(f"\n[{numero:02d}] {descripcion}")  # Encabezado de la operación
        resultado = None  # Valor por defecto si algo falla
        try:
            resultado = operacion(*args, **kwargs)  # Intentamos la operación
        except SoftwareFJError as error:
            # Error de negocio esperado: se registra y se informa
            self._fallidas += 1
            causa = f" | causa: {type(error.__cause__).__name__}: {error.__cause__}" if error.__cause__ else ""
            registrar_evento("ERROR", f"Op {numero:02d} '{descripcion}' falló: {error}{causa}")
            print(f"   ✘ {type(error).__name__}: {error}")
            if error.__cause__:  # Mostramos el error original encadenado
                print(f"     ↳ causado por {type(error.__cause__).__name__}: {error.__cause__}")
        except Exception as error:  # noqa: BLE001 - red de seguridad a propósito
            # Error inesperado de Python: se guarda con todo el detalle (traceback)
            self._fallidas += 1
            # Se guarda el tipo y el detalle completo (traceback) para poder corregirlo
            registrar_evento("CRITICAL", f"Op {numero:02d} '{descripcion}': error inesperado {type(error).__name__}: {error}\n{traceback.format_exc()}")
            print(f"   ✘ Error inesperado ({type(error).__name__}: {error}). El sistema sigue activo.")
        else:
            # Sin errores
            self._exitosas += 1
            registrar_evento("INFO", f"Op {numero:02d} '{descripcion}' completada")
            if resultado is not None:  # Mostramos lo que devolvió la operación
                print(f"   ✔ {resultado}")
            else:
                print("   ✔ Operación completada")
        finally:
            # Siempre se ejecuta: dejamos constancia de que la operación terminó
            registrar_evento("DEBUG", f"Op {numero:02d} finalizada (exitosas={self._exitosas}, fallidas={self._fallidas})")
        return resultado

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    def registrar_cliente(self, **datos):
        """Crea un cliente y lo guarda. No permite documentos repetidos."""
        documento = str(datos.get("documento", "")).strip()  # Documento recibido
        if any(c.documento == documento for c in self._clientes):  # ¿Ya existe?
            raise ClienteInvalidoError(f"Ya existe un cliente con el documento terminado en {documento[-4:]}")
        try:
            cliente = Cliente(**datos)  # Puede lanzar DatoInvalidoError o ParametroFaltanteError
        except (DatoInvalidoError, ParametroFaltanteError) as error:
            # Encadenamos: el error de dato queda como causa del error de cliente
            raise ClienteInvalidoError("No se pudo registrar el cliente") from error
        except TypeError as error:
            # Se envió un campo que Cliente no conoce (ej. "edad")
            raise ClienteInvalidoError("Se enviaron campos desconocidos para el cliente") from error
        self._clientes.append(cliente)  # Lo guardamos en la lista
        return cliente

    def buscar_cliente(self, documento):
        """Devuelve el cliente con ese documento o lanza ClienteInvalidoError."""
        for cliente in self._clientes:  # Recorremos la lista
            if cliente.documento == str(documento):
                return cliente
        raise ClienteInvalidoError(f"No hay ningún cliente registrado con el documento {documento}")

    # ------------------------------------------------------------------
    # Servicios
    # ------------------------------------------------------------------

    def crear_servicio(self, tipo, **datos):
        """Crea un servicio del tipo indicado ('sala', 'equipo' o 'asesoria')."""
        try:
            clase = TIPOS_SERVICIO[tipo]  # KeyError si el tipo no existe
        except KeyError as error:
            raise ServicioInvalidoError(
                f"El tipo de servicio '{tipo}' no existe. Opciones: {', '.join(TIPOS_SERVICIO)}"
            ) from error
        try:
            servicio = clase(**datos)  # Cada clase valida sus propios datos
        except ParametroFaltanteError as error:
            raise ServicioInvalidoError(f"No se pudo crear el servicio '{tipo}'") from error
        except TypeError as error:
            raise ServicioInvalidoError(f"Datos desconocidos para el servicio '{tipo}'") from error
        self._servicios.append(servicio)  # Lo guardamos en la lista
        return servicio

    def buscar_servicio(self, servicio_id):
        """Devuelve el servicio con ese ID o lanza ServicioInvalidoError."""
        for servicio in self._servicios:  # Recorremos la lista
            if servicio.id == str(servicio_id).strip().upper():  # Acepta "srv-0001"
                return servicio
        raise ServicioInvalidoError(f"No existe el servicio {servicio_id}")

    # ------------------------------------------------------------------
    # Reservas
    # ------------------------------------------------------------------

    def crear_reserva(self, documento, servicio_id, duracion, **detalles):
        """Crea una reserva PENDIENTE para un cliente y un servicio registrados."""
        cliente = self.buscar_cliente(documento)          # Puede fallar si no existe
        servicio = self.buscar_servicio(servicio_id)      # Puede fallar si no existe
        reserva = Reserva(cliente, servicio, duracion, **detalles)  # Valida duración y detalles
        self._reservas.append(reserva)                    # La guardamos en la lista
        return reserva

    def buscar_reserva(self, reserva_id):
        """Devuelve la reserva con ese ID o lanza ReservaInvalidaError."""
        for reserva in self._reservas:  # Recorremos la lista
            if reserva.id == str(reserva_id).strip().upper():  # Acepta "res-0001"
                return reserva
        raise ReservaInvalidaError(f"No existe la reserva {reserva_id}")

    def listar(self, tipo):
        """Devuelve la lista pedida ('clientes', 'servicios' o 'reservas') como copia."""
        listas = {"clientes": self._clientes, "servicios": self._servicios, "reservas": self._reservas}
        return list(listas[tipo])  # Copia: quien la recibe no puede dañar la lista interna

    def reservar(self, documento, servicio_id, duracion, **detalles):
        """Crea la reserva y la confirma en un paso.
        Si el servicio no está disponible, la reserva queda CANCELADA y el error sube."""
        reserva = self.crear_reserva(documento, servicio_id, duracion, **detalles)  # Queda PENDIENTE
        try:
            reserva.confirmar()  # Intentamos apartar el servicio
        except ServicioNoDisponibleError:
            reserva.cancelar("rechazada: servicio no disponible")  # No dejamos reservas colgadas
            raise  # El que llamó se entera del error original
        return reserva

    # ------------------------------------------------------------------
    # Reporte final
    # ------------------------------------------------------------------

    def reporte(self):
        """Imprime el estado completo del sistema."""
        linea = "=" * 78  # Separador visual
        print(f"\n{linea}\nREPORTE FINAL - SOFTWARE FJ\n{linea}")
        print(f"\nClientes registrados ({len(self._clientes)}):")
        for c in self._clientes:  # Polimorfismo: cada objeto usa su propio describir()
            print("  -", c)
        print(f"\nServicios ({len(self._servicios)}):")
        for s in self._servicios:
            print("  -", s)
        print(f"\nReservas ({len(self._reservas)}):")
        for r in self._reservas:
            print("  -", r)
        # Sumamos solo las reservas procesadas (las que realmente se cobraron)
        ingresos = sum(r.costo_total for r in self._reservas if r.estado == PROCESADA)
        print(f"\nIngresos procesados: {formato_pesos(ingresos)}")
        if self._exitosas or self._fallidas:  # Solo aplica cuando se usó ejecutar() (simulación)
            print(f"Operaciones exitosas: {self._exitosas} | fallidas y controladas: {self._fallidas}")
        print(linea)
        registrar_evento("INFO", f"Reporte: {len(self._clientes)} clientes, {len(self._servicios)} servicios, "
                                 f"{len(self._reservas)} reservas, ingresos {formato_pesos(ingresos)}")
