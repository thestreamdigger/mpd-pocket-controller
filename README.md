# MPD-Pocket-Controller

A compact Raspberry Pi interface for MPD-based audio systems like moOde, featuring an OLED display and physical controls.

## Features

- OLED display for song information
- 4 configurable buttons for playback control
- RGB LED for status indication
- Supports shuffle mode and USB music file copying
- Ideal for portable and space-constrained audio projects

## Hardware

- Raspberry Pi (compatible with various models)
- SSD1306 OLED Display (128x64 pixels, I2C)
- RGB LED (WS281x)
- 4 physical buttons
- Optional USB storage for music files

## Configuration

Buttons and LED are connected to configurable GPIO pins. The interface can be adapted for various setups, from minimal to extended controls, including options for rotary encoders or headless operation.

## Software Requirements

- Raspberry Pi OS
- moOde audio system
- Python 3
- Required Python libraries (see INSTALL.md)

## Installation

Refer to [INSTALL.md](INSTALL.md) for detailed setup instructions.

## Usage

- Control moOde playback with the buttons
- View song info on the OLED display
- RGB LED indicates playback status

## Contributing

Contributions are welcome. Please submit pull requests or open issues for improvements or bug reports.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.
