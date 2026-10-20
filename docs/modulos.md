# Editar módulos .dmodule

Los nombres de los módulos y sus etiquetas son contenido del circuito. Se muestran tal como están guardados, aunque cambies el idioma de la aplicación.

Haz doble clic sobre un módulo para abrir su editor. También puedes usar clic derecho → Cambiar aspecto. Ambos accesos abren el mismo editor, con tres pestañas:

- **Etiquetas**: cambia el nombre del módulo y los nombres de entradas y salidas. Selecciona una fila y usa **Subir** o **Bajar** para cambiar su posición de arriba abajo. El ancho de cada señal se muestra como referencia. Los cables permanecen conectados a su puerto original; el orden de la tabla lógica, los buses y las conexiones internas se adapta a la nueva disposición.
- **Aspecto**: ajusta colores y redondeado. Restablecer aspecto prepara los valores predeterminados y permite cancelar sin aplicarlos.
- **Simulación**: ajusta el retardo de señal y el retraso de cálculo.

Los botones tienen funciones distintas:

| Botón | Resultado |
| --- | --- |
| Aceptar | Aplica los cambios al módulo del circuito. No modifica el .dmodule. Puedes deshacer la edición en el circuito. |
| Guardar | Actualiza el archivo .dmodule de origen y aplica los cambios al circuito. Si aún no tiene archivo, crea uno en la biblioteca sin sobrescribir otro. |
| Cancelar | Descarta la edición pendiente, incluidos nombre, etiquetas, orden, retardos y aspecto. |

Guardar conserva el archivo de origen aunque cambies el nombre mostrado del módulo; no crea un archivo duplicado. La biblioteca se actualiza después de guardar. Si falla la escritura, el editor permanece abierto y conserva el módulo y el archivo anterior. Los módulos ya colocados en otros puntos del circuito mantienen su propia configuración.

El guardado del .dmodule es independiente del guardado del proyecto. Deshacer una edición en el circuito no revierte el archivo de la biblioteca.
