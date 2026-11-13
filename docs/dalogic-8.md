# DaLogic-8 y pantallas

## Montar un ordenador

1. Coloca **CPU DaLogic-8** y **ROM de programa** desde la pestaña **Memoria**.
2. Une **PC → ADDR** y **Q → INST**. PC es la dirección de 8 bits que la CPU pide a la ROM. Q devuelve la instrucción de 16 bits.
3. Conecta un reloj o un interruptor a **CLK**. Conecta un segundo interruptor a **RESET**. Cada subida de CLK ejecuta una instrucción.
4. Conecta **A** a una salida de bus de 8 bits para ver el acumulador. Opcionalmente, conecta una entrada de bus de 8 bits a **IN** para leer datos externos.
5. Haz clic derecho en la ROM y elige **Editar**. Escribe el programa, compruébalo y pulsa **Cargar en ROM**. Sube RESET y vuelve a bajarlo antes de arrancar. RESET pone a cero PC, A y la RAM de 256 bytes.

## Programar

La ROM admite 256 palabras. Cada palabra contiene el código de operación en los 8 bits superiores y el operando en los 8 inferiores. La interfaz muestra el repertorio completo. Los números del ensamblador se pueden escribir en decimal, hexadecimal (`0x`) o binario (`0b`). Usa etiquetas con `:` y comentarios con `;` o `#`. El modo **Binario** admite una instrucción de 16 bits por línea. Puedes separar ambos bytes con un espacio.

| Código | Instrucción | Operación |
| --- | --- | --- |
| 00 | NOP | Avanza sin modificar A |
| 01 | LDI valor | Carga un byte en A |
| 02 | LDA dirección | Lee la RAM en A |
| 03 | STA dirección | Escribe A en RAM |
| 04–08 | ADD, SUB, AND, OR, XOR dirección | Opera con A y el byte de RAM |
| 09 | JMP dirección | Salta a la dirección |
| 0A | JZ dirección | Salta si A es cero |
| 0B | JNZ dirección | Salta si A es distinto de cero |
| 0C | IN | Lee la entrada IN en A |
| 0D | OUT puerto | Envía A a un puerto de vídeo o solicita el dibujo |
| 0E | HLT | Detiene la CPU hasta RESET |

La aritmética y PC operan módulo 256. Las instrucciones sin operando codifican el byte inferior como 0. Las direcciones de ROM vacías contienen NOP. Por ejemplo, el programa `LDI 42` seguido de `HLT` tiene esta codificación:

```text
00000001 00101010
00001110 00000000
```

## Mostrar píxeles

En **E/S**, elige **Matriz RGB** para LED redondos o **Pantalla de píxeles** para celdas cuadradas. En **Editar** puedes elegir entre 1 y 64 filas, entre 1 y 64 columnas y un tamaño de 4 a 32 px por celda. Al cambiar las dimensiones, se conservan las celdas que siguen dentro de la pantalla.

- **X** y **Y** usan 6 bits y parten de (0,0) en la esquina superior izquierda.
- **RGB** usa 24 bits en el orden `0xRRGGBB`. Cada canal va de 0 a 255.
- **CLK** escribe un píxel en el flanco ascendente. Las coordenadas fuera de la pantalla se ignoran. Un color indeterminado se muestra en ámbar.
- **CLR** borra la pantalla mientras está a 1.

Para dibujar desde la CPU, une sus salidas **X**, **Y** y **RGB** a las entradas homónimas y conecta **PLOT → CLK**. Los puertos de `OUT` son **X (0)**, **Y (1)**, **R (2)**, **G (3)**, **B (4)** y **PLOT (5)**. El pulso de PLOT se emite en la bajada del reloj, después de que los datos estén disponibles. Este ejemplo dibuja un píxel verde en (2,3).

```asm
LDI 2
OUT X
LDI 3
OUT Y
LDI 255
OUT G
OUT PLOT
HLT
```
