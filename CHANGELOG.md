# Changelog

## [1.1.0]

### Añadido

- Componente **Reloj** con intervalo de cambio configurable entre 10 y 60.000 ms (500 ms por defecto).
- Control para pausar o reanudar todos los relojes del circuito desde la barra de herramientas o con **F6**.
- Circuitos secuenciales y realimentación: los CI secuenciales guardan el circuito interno y cada instancia mantiene su propio estado.
- Detección de oscilaciones y bucles de señal, con detención de la simulación y pausa de los relojes.
- Persistencia del estado lógico de los componentes y de los CI secuenciales en los proyectos.
- Documentación sobre relojes, retardos, tablas combinacionales y circuitos con memoria.

### Cambiado

- Los relojes conectados se incluyen como entradas binarias al calcular una tabla de verdad; durante el cálculo permanecen estáticos.
- Los circuitos con realimentación y los CI secuenciales no generan tablas de verdad combinacionales.
- Los archivos `.dmodule` usan el formato publicado **1** para CI combinacionales y el formato **1.1** para CI secuenciales.
- Se conserva la compatibilidad con el formato combinacional publicado 1; se rechazan los archivos de prueba antiguos que empaquetaban sus filas como una lista plana de enteros.
- Los catálogos de idioma se limitan a cadenas visibles de la interfaz.

### Corregido

- Al eliminar componentes o cables, cortar, deshacer o rehacer se reconstruyen las conexiones y se recalculan las señales para quitar activaciones obsoletas.
- Al abrir o reconstruir un proyecto se restauran las conexiones, los estados guardados y la sincronización de los relojes.
