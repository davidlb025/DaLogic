# Programar circuitos propios

En un proyecto de DaLogic, haz clic derecho en una **ROM** o **RAM** y elige **Programar memoria…**. Usa **Editar** para ajustar antes el ancho de los datos y de la dirección. El bloque admite de 1 a 32 bits por palabra y de 1 a 12 bits de dirección.

El circuito pone una dirección en **ADDR** y recibe la palabra en **Q**. Puedes suministrar las direcciones desde una entrada de bus, un contador o un contador de programa hecho con tus propias puertas. Para ejecutar instrucciones, diseña el decodificador y la lógica que dan significado a los bits de Q. La RAM también puede recibir escrituras desde el circuito mediante **D**, **WE** y **CLK**.

## Definir instrucciones

En **Instrucciones**, escribe una regla por línea. A la izquierda van el nombre y los operandos. A la derecha van los bits fijos y los campos de operandos. Usa una letra distinta para cada operando y repite su letra una vez por cada bit de ese campo. El bit más significativo de cada campo se emite primero.

Ejemplo para una memoria de **8 bits**:

```text
NOP       = 0000 0000
CARGA v   = 0001 vvvv
COPIA d,s = 0010 ddss
SALTA a   = 0011 aaaa
EXT v     = 0100 0000 | vvvvvvvv
FIN       = 1111 1111
```

El carácter `|` separa palabras de la misma instrucción. Las etiquetas guardan la dirección de palabra, así que una instrucción de dos palabras ocupa dos direcciones. Puedes guardar y reutilizar la definición como archivo `.isa` de DaLogic.

## Escribir y comprobar

En **Programa**, selecciona **Ensamblador** para usar las instrucciones definidas o **Binario** para introducir una palabra exacta por línea.

```asm
.equ R1 1
inicio:
    CARGA 5
    COPIA R1, 0
    SALTA fin
    EXT 0xA5
fin: FIN
```

Los operandos admiten decimal, hexadecimal `0x`, binario `0b` y etiquetas. Los números negativos se codifican en complemento a dos en el ancho del campo. Usa `.word` para emitir palabras directamente y `; ` o `#` para comentarios. **Comprobar** muestra dirección, hexadecimal y binario. **Cargar en memoria** escribe el programa en el bloque, rellena las direcciones restantes con cero y guarda el texto con el proyecto.

## Construir la memoria con puertas

**Exportar ROM de puertas…** crea un proyecto con interruptores de dirección, puertas AND, OR y NOT y bombillas de datos. Sirve para inspeccionar o reutilizar la lógica de una imagen de hasta 16 palabras y 16 bits por palabra. Para cambiar ese programa cableado, exporta una imagen nueva.
