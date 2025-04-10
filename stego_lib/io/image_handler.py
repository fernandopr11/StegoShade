"""
Manejo de imágenes para esteganografía.
"""

import numpy as np
from PIL import Image
from stego_lib.formats.header import StegoHeader
from stego_lib.utils.debug import log_debug, time_it


class ImageContainer:
    """Gestiona la lectura y escritura de datos en imágenes."""

    def __init__(self, bits_per_channel=2):
        """
        Inicializa el contenedor de imágenes.

        Args:
            bits_per_channel: Número de bits a modificar por canal (1-4)
        """
        if not 1 <= bits_per_channel <= 4:
            raise ValueError("El número de bits por canal debe estar entre 1 y 4")

        self.bits_per_channel = bits_per_channel
        self.mask = (1 << bits_per_channel) - 1
        self.inverse_mask = 0xFF & ~self.mask

    def calculate_capacity(self, image_path):
        """
        Calcula cuántos bytes se pueden ocultar en una imagen.

        Args:
            image_path: Ruta a la imagen

        Returns:
            int: Capacidad en bytes
        """
        try:
            img = Image.open(image_path)
            width, height = img.size

            # Total de píxeles disponibles
            total_pixels = width * height

            # Bits disponibles (3 canales × bits por canal)
            available_bits = total_pixels * 3 * self.bits_per_channel

            # Convertir a bytes
            available_bytes = available_bits // 8

            # Restar el tamaño del encabezado
            available_bytes -= StegoHeader.SIZE

            return max(0, available_bytes)
        except Exception as e:
            raise IOError(f"Error al calcular la capacidad de {image_path}: {e}")

    @time_it
    def calculate_batch_capacity(self, image_paths):
        """
        Calcula la capacidad total, usada y restante de un conjunto de imágenes.

        Args:
            image_paths: Lista de rutas a imágenes PNG

        Returns:
            tuple: (capacidad_total, capacidades_individuales, info_espacio)
                   donde info_espacio contiene (usado, disponible, total) para cada imagen
        """
        total_capacity = 0
        individual_capacities = {}
        space_info = {}  # Nuevo diccionario para almacenar información de espacio

        log_debug(f"Calculando capacidad para {len(image_paths)} imágenes")

        for path in image_paths:
            capacity = self.calculate_capacity(path)
            individual_capacities[path] = capacity
            total_capacity += capacity

            # Calcular espacio usado y disponible
            try:
                # Leer datos existentes para determinar el espacio usado
                used_segments = self.find_used_segments(path)
                bytes_used = sum(segment_size for _, segment_size in used_segments)
                bytes_available = capacity - bytes_used

                # Guardar la información de espacio
                space_info[path] = (bytes_used, bytes_available, capacity)

                # Log detallado con información de uso
                percent_used = (bytes_used / capacity * 100) if capacity > 0 else 0
                log_debug(f"  - {path}: {capacity} bytes ({capacity / 1024:.2f} KB) | "
                          f"Usado: {bytes_used} bytes ({percent_used:.1f}%) | "
                          f"Disponible: {bytes_available} bytes | "
                          f"Mensajes: {len(used_segments)}")

            except Exception as e:
                log_debug(f"  - {path}: Error al analizar espacio: {e}")
                space_info[path] = (0, capacity, capacity)  # En caso de error, asumimos vacía

        log_debug(f"Capacidad total: {total_capacity} bytes ({total_capacity / 1024:.2f} KB)")

        # Calcular totales de espacio usado/disponible
        total_used = sum(used for used, _, _ in space_info.values())
        total_available = sum(available for _, available, _ in space_info.values())

        percent_used_total = (total_used / total_capacity * 100) if total_capacity > 0 else 0
        log_debug(f"Espacio total usado: {total_used} bytes ({total_used / 1024:.2f} KB) - {percent_used_total:.1f}%")
        log_debug(f"Espacio total disponible: {total_available} bytes ({total_available / 1024:.2f} KB)")

        return total_capacity, individual_capacities, space_info

    def find_used_segments(self, image_path):
        """
        Encuentra los segmentos de datos ya utilizados en una imagen.

        Args:
            image_path: Ruta de la imagen a analizar

        Returns:
            list: Lista de tuplas (offset_byte, tamaño_segmento) de segmentos usados
        """
        segments = []
        try:
            # Extraer todos los bits de la imagen
            raw_data = self.extract_all_bits(image_path)
            if not raw_data or len(raw_data) < StegoHeader.SIZE:
                return segments

            # Buscar encabezados de mensajes en los datos extraídos
            offset = 0
            while offset + StegoHeader.SIZE <= len(raw_data):
                try:
                    header = StegoHeader.parse(raw_data[offset:offset + StegoHeader.SIZE])
                    segment_size = StegoHeader.SIZE + min(
                        len(raw_data) - offset - StegoHeader.SIZE,
                        header.total_length - header.current_offset
                    )
                    segments.append((offset, segment_size))

                    # Saltar al siguiente posible segmento
                    offset += segment_size
                except Exception:
                    # Si no se puede parsear el encabezado, avanzar 1 byte
                    offset += 1

            return segments
        except Exception as e:
            log_debug(f"Error al buscar segmentos en {image_path}: {e}")
            return segments

    def extract_all_bits(self, image_path):
        """
        Extrae todos los bits de una imagen sin procesar.
        Similar a read_data pero sin interpretar el contenido.
        """
        try:
            # Cargar la imagen
            img = Image.open(image_path).convert('RGB')

            # Convertir a numpy array
            pixels = np.array(img)
            pixels_flat = pixels.reshape(-1)

            # Extraer todos los bits ocultos de una vez
            extracted_bits = []
            for pixel_value in pixels_flat:
                for j in range(self.bits_per_channel):
                    extracted_bits.append((pixel_value >> j) & 1)

            # Convertir los bits a bytes
            data = bytearray()
            for i in range(0, len(extracted_bits), 8):
                if i + 8 > len(extracted_bits):
                    break
                byte = 0
                for j in range(8):
                    byte = (byte << 1) | extracted_bits[i + j]
                data.append(byte)

            return bytes(data)
        except Exception as e:
            raise IOError(f"Error al extraer bits de {image_path}: {e}")

    def write_data(self, input_path, output_path, data):
        """
        Escribe datos en una imagen utilizando esteganografía sin sobrescribir mensajes existentes.

        Args:
            input_path: Ruta de la imagen original
            output_path: Ruta donde guardar la imagen con datos ocultos
            data: Bytes a ocultar

        Returns:
            bool: True si la operación fue exitosa
        """
        try:
            # Cargar la imagen
            img = Image.open(input_path).convert('RGB')
            width, height = img.size

            # Convertir a numpy array para procesar más rápido
            pixels = np.array(img)
            pixels_flat = pixels.reshape(-1)

            # Encontrar segmentos ya utilizados
            used_segments = self.find_used_segments(input_path)

            # Calcular el primer byte libre
            next_free_byte = 0
            for offset, size in used_segments:
                next_free_byte = max(next_free_byte, offset + size)

            # Verificar que hay espacio suficiente
            max_bytes = (len(pixels_flat) * self.bits_per_channel) // 8
            if next_free_byte + len(data) > max_bytes:
                raise ValueError(f"No hay suficiente espacio en la imagen para {len(data)} bytes")

            # Convertir los datos a bits
            bits = []
            for byte in data:
                for i in range(7, -1, -1):
                    bits.append((byte >> i) & 1)

            # Rellenar con ceros si es necesario para completar un byte
            if len(bits) % self.bits_per_channel != 0:
                bits.extend([0] * (self.bits_per_channel - (len(bits) % self.bits_per_channel)))

            # Calcular qué bits tenemos que modificar
            start_bit = next_free_byte * 8

            # Modificar solo los bits necesarios
            bit_index = 0
            for i in range(len(pixels_flat)):
                # Calcular el índice del bit en la secuencia plana
                current_bit = i * self.bits_per_channel

                # Si estamos antes del inicio o ya terminamos, continuar
                if current_bit < start_bit:
                    continue
                if bit_index >= len(bits):
                    break

                # Limpiar los bits que vamos a modificar
                pixels_flat[i] = pixels_flat[i] & self.inverse_mask

                # Escribir los nuevos bits
                bits_to_write = min(self.bits_per_channel, len(bits) - bit_index)
                for j in range(bits_to_write):
                    pixels_flat[i] |= (bits[bit_index] << j)
                    bit_index += 1
                    if bit_index >= len(bits):
                        break

            # Reconstruir la imagen
            stego_img = Image.fromarray(pixels.reshape(height, width, 3))

            # Guardar la imagen resultante
            stego_img.save(output_path, quality=100)

            log_debug(f"Datos escritos en {output_path}: {len(data)} bytes a partir del byte {next_free_byte}")
            return True
        except Exception as e:
            raise IOError(f"Error al escribir datos en {input_path}: {e}")

    def read_data(self, image_path):
        """
        Lee datos ocultos en una imagen.
        Devuelve el primer mensaje completo encontrado.
        """
        try:
            # Extraer todos los bits
            raw_data = self.extract_all_bits(image_path)
            if not raw_data or len(raw_data) < StegoHeader.SIZE:
                return None

            # Buscar todos los mensajes
            messages = []
            offset = 0

            while offset + StegoHeader.SIZE <= len(raw_data):
                try:
                    header = StegoHeader.parse(raw_data[offset:offset + StegoHeader.SIZE])

                    # Determinar cuánto del mensaje está en esta imagen
                    message_part_size = min(
                        len(raw_data) - offset - StegoHeader.SIZE,
                        header.total_length - header.current_offset
                    )

                    # Extraer el mensaje completo
                    message_data = raw_data[offset:offset + StegoHeader.SIZE + message_part_size]
                    messages.append(message_data)

                    # Saltar al siguiente posible mensaje
                    offset += StegoHeader.SIZE + message_part_size
                except Exception:
                    # Si no podemos parsear el encabezado, avanzamos un byte
                    offset += 1

            # Devolver el primer mensaje completo si hay alguno
            return messages[0] if messages else None

        except Exception as e:
            raise IOError(f"Error al leer datos de {image_path}: {e}")

    def read_all_messages(self, image_path):
        """
        Lee todos los mensajes ocultos en una imagen.

        Args:
            image_path: Ruta a la imagen

        Returns:
            list: Lista de mensajes extraídos
        """
        try:
            # Extraer todos los bits
            raw_data = self.extract_all_bits(image_path)
            if not raw_data or len(raw_data) < StegoHeader.SIZE:
                return []

            # Buscar todos los mensajes
            messages = []
            offset = 0

            while offset + StegoHeader.SIZE <= len(raw_data):
                try:
                    header = StegoHeader.parse(raw_data[offset:offset + StegoHeader.SIZE])

                    # Determinar cuánto del mensaje está en esta imagen
                    message_part_size = min(
                        len(raw_data) - offset - StegoHeader.SIZE,
                        header.total_length - header.current_offset
                    )

                    # Extraer el mensaje completo
                    message_data = raw_data[offset:offset + StegoHeader.SIZE + message_part_size]
                    messages.append(message_data)

                    # Saltar al siguiente posible mensaje
                    offset += StegoHeader.SIZE + message_part_size
                except Exception:
                    # Si no podemos parsear el encabezado, avanzamos un byte
                    offset += 1

            return messages

        except Exception as e:
            raise IOError(f"Error al leer datos de {image_path}: {e}")