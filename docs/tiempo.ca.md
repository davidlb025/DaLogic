# Temps i realimentació

El DaLogic propaga senyals amb una cua d'esdeveniments. El retard en mil·lisegons i les etapes de porta addicionals determinen quan els canvis arriben a la destinació. Les etapes i el temps transcorregut representen aspectes diferents de la propagació. L'interval d'un rellotge determina quan commuta.

F6 pausa els rellotges mentre la propagació pot continuar. F8 pausa tota la simulació i conserva els esdeveniments. F10 aplica el següent lot simultani; si la cua és buida, pot avançar els rellotges. Les sondes permeten examinar l'historial. F9 alterna punts d'aturada als components seleccionats; un canvi a l'entrada atura la simulació.

## Realimentació i estat

Una taula combinacional representa sortides que només depenen de les entrades actuals. Un circuit amb realimentació, memòria, comptador o registre també depèn de l'estat anterior. Per això no se'n calcula una taula de veritat combinacional. Utilitza simulació, passos i sondes per observar-ne l'evolució.

Crea un CI seqüencial per conservar la xarxa i la memòria dins d'un mòdul reutilitzable. Cada instància té un estat independent. Els projectes en conserven l'estat en desar i obrir. El format `.dmodule` es tria segons el contingut: 1 desa taules escalars; 1.1 desa xarxes seqüencials escalars; 1.2 incorpora busos i X/Z a les taules; 1.3 afegeix memòria nativa i busos a les xarxes seqüencials.

Una realimentació inestable pot produir X. Si es detecta una oscil·lació o un bucle infinit, la simulació s'atura i els rellotges es pausen. Revisa les connexions i els retards abans de reprendre. Les parts independents poden continuar quan una xarxa local inestable es resol com a X.

## Sondes i diagnòstic

Ctrl+clic en un cable o port afegeix una sonda. La capacitat va de 256 a 100.000 canvis per senyal. Descartar mostres antigues no modifica el circuit. CSV exporta esdeveniments tabulats; VCD exporta ones amb marques temporals. Les captures són a la memòria fins que s'exporten o s'esborren.

F7 informa d'entrades lliures, xarxes sense font, amplades incompatibles, conflictes de controladors tri-state, extrems lliures i senyals X. Alguns ports lliures són intencionats. Fes doble clic en una incidència per localitzar l'element. El diagnòstic no modifica l'estat elèctric.

En connectar o eliminar components, l'editor reconstrueix la topologia sense generar polsos artificials de rellotge. La memòria nativa i els mòduls seqüencials imbricats conserven l'estat. X és un valor indeterminat; Z representa un bus alliberat. Cap dels dos s'ha d'interpretar com a cert.
