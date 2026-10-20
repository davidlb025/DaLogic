# Components

Ports follow the visible order. Bus widths must match when connecting components. X means unknown and Z means high impedance. A logic 1 dominates a wired-OR network; unknown values remain observable. Tri-state outputs drive the bus only while enabled. Pull-up and pull-down provide weak default values.

## Basic and bus components

AND, OR, XOR, NOT, NAND and NOR implement their usual truth tables. Configurable gates accept 2–8 inputs. Switches toggle on double-click; buttons remain active while pressed. Clocks generate square waves. Delay adds a configurable propagation delay. Bulbs show a one-bit signal; seven-segment displays accept individual segment inputs and configurable colors.

Bus Input supplies an unsigned integer between 2 and 32 bits. Bus Output shows its decimal and hexadecimal value. Bus Viewer observes a connected bit or bus without changing its value. Splitter exposes individual bits with bit 0 at the top; Combiner assembles bits into a bus. Tri-state uses its data input and enable input to drive a bus or release it to Z.

## Arithmetic and selection

| Component | Behavior |
| --- | --- |
| Adder | A + B + carry-in, with a result bus and carry-out |
| Adder / subtractor | Adds or subtracts according to SUB; includes carry or borrow |
| Comparator | Compares two bus values |
| ALU | Selects arithmetic and bitwise operations through its control input |
| Multiplexer | Routes one selected data input to its output |
| Demultiplexer | Routes data to one selected output |
| Decoder | Activates the output corresponding to a binary input |
| BCD to seven segments | Converts a BCD value to display segments |

Configure data width and channel count through the component's context menu where supported. Available channel counts are 2, 4, 8 and 16.

## Memory and registers

RAM and ROM use configurable address bits, up to 4096 words, and configurable word width. Edit contents with decimal or hexadecimal words separated by spaces; X represents an unknown word. Remaining addresses are filled with zero. Import contents from a text file in the memory dialog.

RAM writes on a rising clock edge when enabled. ROM retains its programmed contents. Counters and shift registers also react to clock transitions and their control inputs. Saved projects preserve native memory and register state. Sequential modules can encapsulate memory with format 1.3; different module instances have independent states.

## Inputs and peripherals

DIP switches and the hexadecimal keypad provide editable input values. Constants provide fixed bus values. LED bars show individual bits. Numeric displays show a bus value. An LED matrix supports 2–32 LEDs arranged in rows, with bit 0 at the top left. RGB LEDs accept R, G and B channels. Traffic lights show their three input signals. The buzzer can play sound when its input is 1; sound is optional in its settings.

## Visual elements

Text, squares, circles and planes decorate and organize a circuit. Double-click or right-click to edit. Select an element to resize it. Configure text font, size, weight, color and opacity, and shape fill, border and corner radius as applicable. A plane always retains its frame and requires a unique nonempty name. These elements have no ports and do not affect simulation.
