# Componentes de DaLogic 1.2.0

Las pestañas **Aritmética**, **Memoria** y **E/S** aparecen entre **Básico** y **CI**. Clic derecho abre la configuración; los puertos muestran sus nombres y anchos. Los datos son enteros sin signo de 1–32 bits en los bloques nativos. La entrada numérica de bus existente acepta decimal y hexadecimal (`0xFF`) y usa 2–32 bits.

## Aritmética y selección

| Bloque | Entradas, de arriba abajo | Salidas | Comportamiento |
| --- | --- | --- | --- |
| Sumador | A, B, Cin | S, Cout | Suma modular; Cout indica acarreo. |
| Sumador/restador | A, B, SUB | R, C/B | SUB=0 suma; SUB=1 resta. C/B es acarreo al sumar y préstamo al restar. |
| Comparador | A, B | =, >, < | Comparación sin signo. |
| ALU | A, B, OP de 3 bits | R, C/B, Z | OP: 0 suma; 1 resta; 2 AND; 3 OR; 4 XOR; 5 desplazamiento de A a la izquierda un bit; 6 a la derecha; 7 NOT A. Z=1 si R=0; C/B indica acarreo/préstamo o bit expulsado. |
| MUX | D0…Dn, SEL | Y | Selecciona una entrada; 2, 4, 8 o 16 canales y ancho de datos configurable. |
| DEMUX | D, SEL | Y0…Yn | Envía D a una salida y pone las demás a cero. |
| Decodificador | A, EN | Y0…Yn | Con EN=1 activa la línea A; con EN=0 todas a cero. 2, 4, 8 o 16 líneas. |
| BCD → 7 segmentos | BCD de 4 bits | a, b, c, d, e, f, g | Dígitos 0–9; valores 10–15 apagan todos los segmentos. Conectar al display existente. |

Los cálculos se recortan al ancho elegido. Las entradas indeterminadas `X` o flotantes `Z` producen `X` cuando afectan al resultado. Un MUX conserva el valor de su entrada seleccionada, incluso `Z`. El decodificador deshabilitado permanece a cero aunque A sea indeterminado.

## Memoria y registros

Todos los relojes actúan por **flanco ascendente**. Una señal que permanece a 1 no vuelve a escribir ni a contar. Reconstruir conexiones, copiar o abrir un proyecto no genera flancos artificiales.

| Bloque | Entradas | Salidas | Comportamiento |
| --- | --- | --- | --- |
| RAM | ADDR, D, WE, CLK | Q | Escritura en flanco ascendente con WE=1; lectura asíncrona de la dirección actual. |
| ROM | ADDR | Q | Lectura asíncrona del contenido configurado. |
| Contador | CLK, EN, DOWN, LOAD, D, RST | Q | Reset asíncrono prioritario; carga en flanco; con EN=1 cuenta hacia arriba o abajo según DOWN. Desbordamiento modular. |
| Registro de desplazamiento | CLK, EN, SER, RST | Q, SERout | Reset asíncrono. En flanco con EN=1 desplaza a la izquierda e introduce SER en bit 0. SERout refleja el bit más significativo actual. |

RAM y ROM permiten 1–12 bits de dirección: hasta **4096 palabras**, de 1–32 bits cada una. Clic derecho permite editar o importar un archivo de texto. Se aceptan palabras decimales, `0xHEX` o `X`, separadas por espacios, saltos de línea o comas. La primera palabra corresponde a dirección 0; las restantes se rellenan con cero. Se rechazan valores fuera del ancho y contenidos demasiado largos.

Los proyectos `.dalogic`, el historial y las copias de componentes conservan el contenido de memoria, el contador, el registro y el nivel de reloj anterior. La tabla combinacional rechaza RAM, contador y registro. ROM sí es combinacional.

El formato de CI secuencial 1.1 conserva su compatibilidad anterior. Desde DaLogic 1.2, los bloques nativos con memoria se pueden encapsular usando automáticamente el nuevo formato 1.3, con buses y estado por instancia; consulta [Depuración y CI](depuracion-y-ci.md). Los bloques nativos combinacionales sí pueden formar CI con los límites habituales de tamaño de tabla.

## Entradas y salidas

- **DIP switch:** clic en cada casilla alterna un bit; bit 0 arriba a la izquierda. Clic derecho configura ancho y valor.
- **Constante:** fuente de 1–32 bits; valor decimal/hexadecimal configurable. A diferencia de una entrada, su valor se mantiene fijo al calcular tablas de verdad.
- **Entrada de bus:** entrada numérica decimal/hexadecimal existente.
- **Teclado hexadecimal:** dieciséis teclas 0–F; cada clic publica su valor en un bus fijo de 4 bits.
- **Barra de LED:** hasta 32 LED en una única fila; bit 0 a la izquierda.
- **Matriz de LED:** cuadrícula 2D con filas y columnas configurables desde clic derecho, con 2–32 LED en total (por ejemplo 4×4 o 4×8). Bit 0 arriba a la izquierda y bits consecutivos por filas. Las dimensiones se conservan al guardar y copiar. Los proyectos antiguos mantienen su ancho de bus.
- **LED RGB:** tres entradas de 8 bits (0–255) controlan la intensidad de R, G y B de forma independiente. `X` se muestra en ámbar y `Z` como canal apagado.
- **Semáforo:** tres entradas escalares controlan las luces roja, amarilla y verde. Cada luz puede activarse de forma independiente; `X` se muestra en ámbar y `Z` como luz apagada.
- **Display numérico:** lectura decimal y hexadecimal de hasta 32 bits; muestra `X`/`Z` si procede.
- **Indicador sonoro:** habilitar el sonido en su configuración; emite el aviso del sistema al pasar su entrada EN a 1. Está desactivado de forma predeterminada.
- **Pull-up / pull-down:** fuentes débiles de un bit. Fijan entradas liberadas a 1/0 y ceden ante cualquier driver fuerte activo. Se pueden conectar a una misma entrada mediante un nexo.
- Los cables con un puerto multi-bit muestran el valor actual en decimal, hexadecimal y binario. Los tramos interiores entre nexos conservan el comportamiento anterior sin etiqueta adicional.

## Biblioteca

La biblioteca tiene 30 CI, organizados en `Basicos`, `Aritmetica`, `Seleccion`, `Codificacion`, `Comprobacion`, `Buses` y `Secuenciales` (con `Latches` y `Flip-flops`). Los ocho archivos anteriores mantienen sus nombres; el D Latch corrige sus vinculaciones para usar D, EN y salidas Q, Q̅. Los restantes conservan su contenido. Las referencias antiguas a esos archivos se reubican al abrir un proyecto; sus definiciones siguen incluidas dentro del proyecto.

Los 22 CI nuevos tienen puertos identificados y tablas completas. Al abrir proyectos, DaLogic busca las referencias antiguas de módulos por nombre de archivo dentro de la biblioteca, sin sobrescribir módulos existentes.

## Verificación

Con Python y las dependencias instaladas, desde la raíz del proyecto:

```console
python -m unittest discover -s tests -v
```

Las 60 pruebas cubren aritmética exhaustiva de cuatro bits, las ocho operaciones de ALU, selección, BCD, flancos, memoria, todos los CI de biblioteca, persistencia, copia/pegado, señales X/Z, pulls, análisis de buses, diálogos y renderizado Qt.
