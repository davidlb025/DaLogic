# Components

Els ports segueixen l'ordre visible. Les amplades dels busos han de coincidir. X indica un valor indeterminat i Z una alta impedància. Un 1 domina una xarxa wired-OR; els indeterminats continuen visibles. Un controlador tri-state condueix el bus només quan està habilitat. Pull-up i pull-down proporcionen valors febles per defecte.

## Components bàsics i busos

AND, OR, XOR, NOT, NAND i NOR implementen les taules lògiques habituals. Les portes configurables admeten de 2 a 8 entrades. Els interruptors commuten amb doble clic; els botons s'activen mentre es mantenen premuts. Els rellotges generen ones quadrades. Retard afegeix un temps de propagació configurable. Les bombetes mostren un bit; les pantalles de set segments reben entrades individuals i tenen colors configurables.

Entrada de bus subministra un enter sense signe de 2 a 32 bits. Sortida de bus en mostra el valor decimal i hexadecimal. Visor de bus observa un bit o bus sense canviar-lo. Divisor de bus exposa els bits, amb el bit 0 a dalt; Combinador els uneix. Tri-state utilitza dades i habilitació per conduir el bus o deixar-lo en Z.

## Aritmètica i selecció

| Component | Comportament |
| --- | --- |
| Sumador | A + B + acarreament d'entrada, amb resultat i acarreament de sortida |
| Sumador i restador | Suma o resta segons SUB, amb acarreament o préstec |
| Comparador | Compara dos valors de bus |
| ALU | Selecciona operacions aritmètiques i bit a bit |
| Multiplexor | Envia l'entrada seleccionada a la sortida |
| Desmultiplexor | Envia dades a una sortida seleccionada |
| Descodificador | Activa la sortida corresponent a un valor binari |
| BCD a set segments | Converteix un valor BCD als segments d'una pantalla |

El menú contextual configura l'amplada i els canals quan el component ho admet. Els nombres de canals disponibles són 2, 4, 8 i 16.

## Memòria i registres

RAM i ROM tenen bits d'adreça configurables, fins a 4096 paraules, i amplada de paraula configurable. Edita el contingut amb paraules decimals o hexadecimals separades per espais. X representa una paraula indeterminada. Les adreces restants s'omplen amb zero. El diàleg de memòria permet importar text.

La RAM escriu en un flanc ascendent del rellotge quan està habilitada. La ROM conserva el contingut programat. Comptadors i registres de desplaçament responen als flancs i als controls. Els projectes conserven la memòria i l'estat. Els CI seqüencials de format 1.3 poden encapsular memòria; cada instància en conserva un estat independent.

## Entrades i perifèrics

Els interruptors DIP i el teclat hexadecimal proporcionen valors editables. Les constants donen valors fixos. La barra de LED mostra els bits individuals. La pantalla numèrica mostra el valor d'un bus. Una matriu té de 2 a 32 LED, amb el bit 0 a dalt a l'esquerra. El LED RGB rep canals R, G i B. El semàfor representa les tres entrades. L'indicador sonor pot reproduir so amb un 1; l'opció es configura al diàleg.

## Elements visuals

Text, quadrats, cercles i plans decoren i organitzen el circuit. Un doble clic o clic dret permet editar-los; la selecció permet redimensionar-los. Configura el tipus i la mida de lletra, el color, l'opacitat, el farciment, la vora i el radi segons el tipus. Els plans conserven el marc i necessiten un nom únic no buit. Aquests elements no tenen ports ni afecten la simulació.
