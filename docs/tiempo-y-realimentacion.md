# Tiempo, relojes y realimentación

Esta página explica qué mide cada ajuste temporal de DaLogic y cómo se comportan los circuitos con realimentación, como un biestable SR hecho con puertas NOR o NAND.

## Reloj

El componente **Reloj** genera una onda cuadrada. Su propiedad **Intervalo de cambio** indica cuánto espera entre una transición y la siguiente; no es la duración del ciclo completo. Con el valor predeterminado de 500 ms, por ejemplo, cambia de 0 a 1, espera otros 500 ms y cambia de 1 a 0. El ciclo completo dura 1.000 ms (1 s), con mitad del tiempo en cada nivel.

El intervalo se configura con clic derecho → Editar sobre el reloj y admite de 10 a 60.000 ms. El reloj comienza en 0 y la primera transición ocurre al vencer el primer intervalo. Cada reloj del proyecto tiene su propio temporizador, administrado por el tablero. Al cambiar el intervalo, el tablero actualiza el temporizador; al quitar el reloj, lo detiene.

El estado actual y el intervalo se guardan en el proyecto. Al abrirlo, el reloj conserva si estaba en 0 o en 1, pero inicia un nuevo conteo del intervalo: no se guarda la fase ni el tiempo restante del pulso.

Para depurar una secuencia, usa **Pausar relojes** en el menú **Simulación** o pulsa **F6**. El control pausa o reanuda todos los relojes del proyecto; los relojes que añadas mientras está pausado también permanecerán detenidos.

## Retardos y tiempo de respuesta

El ajuste **Retardo de señal (ms)** retrasa la propagación de las señales que recibe; admite de 0 a 10.000 ms. También puedes sumar **Retraso de cálculo**, de 0 a 10.000. Cada puerta lógica básica, CI o componente nativo añade una etapa al recorrido; el retraso de cálculo suma etapas al componente configurado. Así, un camino por tres puertas tarda tres etapas y una puerta con tres extra tarda cuatro. Las etapas se ordenan como unidades de simulación de 1 ms. Las bombillas y displays también admiten ambos ajustes para retrasar la actualización visible.

El tablero procesa las señales pendientes por orden de vencimiento. Si varias tienen el mismo retardo, las procesa en el mismo lote. Una entrada con varios cables combina sus controladores mediante OR: está activa mientras al menos uno de ellos entregue 1. La lógica de un componente se vuelve a calcular cuando cambia una entrada; sus nuevas salidas solo generan señales cuando su valor cambia.

El tiempo que muestra una fila de una tabla combinacional es una **estimación** del camino más largo hasta las salidas: suma retardos configurados y tiempos de respuesta de los módulos. No es una medición del reloj del sistema ni incluye la duración de los ciclos de un reloj.

## Realimentación y memoria

Hay realimentación cuando una salida vuelve, directa o indirectamente, a una entrada anterior del circuito. Por ejemplo, dos puertas NOR cruzadas pueden formar un biestable SR: el estado de sus salidas mantiene la memoria aunque las entradas S y R vuelvan a 0. Por eso la salida depende de la historia del circuito y no solo de la combinación instantánea de entradas.

En la simulación, cada señal que cambia recorre la cola de propagación del tablero y vuelve a activar las puertas afectadas. Las realimentaciones que convergen alcanzan un estado estable. Si el tablero detecta que una realimentación combinacional oscila o no se estabiliza, detiene la simulación, pausa los relojes y muestra un aviso para revisar las conexiones. Añadir un retardo cambia cuándo llegan los eventos, pero no convierte un circuito oscilante en una memoria estable por sí solo.

Al añadir o eliminar conexiones, DaLogic reconstruye la red desde las salidas actuales y actualiza las entradas afectadas. No reinicia la memoria de todos los componentes. Un borrado de varios elementos se resuelve como una sola edición, y no genera pulsos de reloj intermedios. Las señales que llegan en el mismo instante actualizan todas las entradas antes de evaluar la puerta. Al editar, el circuito se ajusta a su estado estable; los retardos configurados se aplican a las transiciones durante la simulación.

Si la red resultante de una edición contiene un bucle que realmente no puede estabilizarse, sus salidas se muestran como **X** y el resto del circuito sigue disponible. Deshacer y rehacer restauran la memoria guardada junto con las conexiones.

Los proyectos guardan las entradas y salidas lógicas vivas de los componentes, de modo que una memoria como el biestable SR puede continuar desde su estado guardado al volver a abrir el proyecto. Si una selección con realimentación se convierte en CI, DaLogic conserva el circuito interno y su estado: crea un **CI secuencial**, y cada instancia tiene memoria propia. Este CI no tiene una tabla de verdad combinacional válida.

## Tabla de verdad y relojes

La tabla combinacional trata interruptores, botones y relojes conectados como entradas binarias y enumera sus combinaciones. En ese cálculo el reloj es una entrada estática de la fila; no avanza en el tiempo ni representa ciclos o formas de onda.

DaLogic no calcula una tabla de verdad para un circuito con conexiones recursivas ni para uno que contiene un CI secuencial. Muestra un aviso porque sus salidas dependen de estados anteriores. Para estudiar una secuencia temporal, ejecuta el circuito en el tablero con uno o más relojes y observa las señales y salidas.
