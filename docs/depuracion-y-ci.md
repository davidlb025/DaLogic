# Depuración y circuitos integrados en DaLogic 1.2

## Pausa y pasos

F6 conserva su función anterior: pausa únicamente los relojes. Las señales pendientes pueden seguir propagándose.

F8 pausa la simulación completa: relojes y propagación. Los eventos con retardo conservan el tiempo restante. Reanudar continúa desde los eventos pendientes.

F10 entra en pausa completa y ejecuta el siguiente lote de cambios simultáneos. Los retardos se avanzan sin esperar físicamente y la barra de estado muestra el avance acumulado y los eventos pendientes. Si no quedan eventos, se alternan manualmente los relojes del circuito y se propagan sus cambios por pasos. Este avance manual no reproduce la separación de fase de relojes con intervalos distintos.

Un punto de parada permite inspeccionar el circuito justo cuando una señal llega a un componente. Selecciona una puerta, un módulo o una salida con entradas y pulsa **F9**, o usa **Simulación → Añadir punto de parada**. Aparece una marca roja. Los interruptores y relojes no reciben entradas y no admiten esta parada.

Cuando cambia una entrada marcada, DaLogic aplica y calcula ese lote simultáneo, pausa los relojes y la propagación, muestra la marca naranja y lleva la vista al componente. Los siguientes eventos quedan pendientes. Pulsa **F10** para ejecutar el siguiente lote o **F8 / Reanudar simulación** para continuar. La parada no se activa otra vez mientras la entrada mantenga el mismo valor.

Por ejemplo, conecta **Interruptor → NOT → Bombilla** y marca NOT con F9. Al cambiar el interruptor, se actualizan la entrada y la salida de NOT, pero la bombilla conserva su estado porque su evento sigue pendiente. F10 aplica ese evento y actualiza la bombilla. Así puedes localizar en qué tramo cambia una señal.

Selecciona los componentes marcados y pulsa F9 para quitar sus puntos de parada. Si la selección mezcla componentes marcados y sin marcar, F9 los marca todos; una segunda pulsación los desmarca. Son ayudas temporales de la sesión: no se guardan en el proyecto y se limpian al abrir, crear o reconstruirlo. Un módulo se observa por sus entradas externas; no se entra en sus nodos internos.

La detección de oscilaciones sigue activa. Los pasos no convierten una realimentación combinacional inestable en un circuito con memoria válido.

## Sondas

En Simulación → Sondas puedes elegir la capacidad de cada historial, entre 256 y 100.000 cambios, con 10.000 por defecto. La capacidad se conserva como preferencia. Reducirla descarta las muestras más antiguas.

Ventana elige cuántos segundos se muestran, entre 0,5 y 600. Retroceder desplaza el final de la vista hacia el pasado hasta 24 horas; usa cero para seguir el presente. La captura continúa mientras inspeccionas una zona anterior. Los controles no crean muestras que ya hayan sido descartadas.

Limpiar historial reinicia el origen temporal y vuelve al presente. Exportar sondas guarda las muestras retenidas en CSV o VCD, aunque la vista esté desplazada. La captura se mantiene en memoria; expórtala antes de cerrar.

## CI con memoria nativa

Selecciona las fuentes de entrada, los componentes internos y las bombillas/salidas de bus que formen el circuito. Usa Widgets → Crear CI y elige el nombre y la carpeta de biblioteca.

El formato 1.3 guarda una red interna de versión 2, con anchos de puerto, parámetros de RAM/ROM, contenido de memoria, contador/registro, reloj previo, conexiones y estado inicial. Cada instancia utiliza copias independientes de esa red y del estado. Un proyecto `.dalogic` conserva también el estado vivo de cada instancia.

Las señales que llegan en un mismo lote se aplican antes de evaluar el componente, para que una memoria no capture el dato anterior cuando cambian dato y reloj simultáneamente. Los retardos internos se conservan en la simulación.

Se pueden anidar CI y utilizar buses de hasta 32 bits por puerto. Los relojes elegidos como fuentes de interfaz son entradas del CI; el CI no incorpora un generador de reloj autónomo. Los periféricos de salida internos conservan su lógica de señales, sin reproducir su interfaz ni generar audio desde dentro del CI.

Los CI anteriores 1, 1.1 y 1.2 siguen siendo compatibles. Los nuevos circuitos que requieren memoria nativa o buses secuenciales se guardan en 1.3 y necesitan DaLogic 1.2.0 o posterior. La numeración del formato de archivo es independiente de la versión de DaLogic. Las tablas combinacionales continúan sin representar memoria ni realimentación.
