import spidev

import numpy

class Freenove_SPI_LedPixel(object):

    """

    SPI-based driver for WS2812/NeoPixel chains used on the Freenove FNK0043.

    Compatible with your existing code (set_led_rgb_data, set_all_led_color, show, etc.)

    Adds a proper WS2812 reset latch after each frame for rock-solid latching.

    """

    def _get_spi_mode_from_params(self):

        try:

            import json

            from pathlib import Path

            # Check config/ directory first, then current directory

            config_path = Path(__file__).parent.parent.parent / "config" / "params.json"

            if not config_path.exists():

                config_path = Path(__file__).parent.parent / "params.json"

            if not config_path.exists():

                config_path = Path("params.json")

            with open(config_path, 'r') as f:

                j = json.load(f)

            m = int(j.get('Spi_Mode', 1))

            return 4 if m == 4 else 1

        except Exception:

            return 1

    def __init__(self, count=60, bright=120, sequence='GRB', bus=0, device=0):

        self.set_led_type(sequence)

        self.set_led_count(count)

        self.set_led_brightness(bright)

        self.led_begin(bus, device)

        self.set_all_led_color(0, 0, 0)

    def led_begin(self, bus=0, device=0):

        self.bus = bus

        self.device = device

        try:

            self.spi = spidev.SpiDev()

            self.spi.open(self.bus, self.device)

            self.spi.mode = 0

            self.led_init_state = 1

        except OSError:

            print("Please check the configuration in /boot/firmware/config.txt.")

            if self.bus == 0:

                print("Enable 'SPI' via 'sudo raspi-config' (Interface Options).")

                print("Or ensure 'dtparam=spi=on' is present, then reboot.")

            else:

                print(f"Add 'dtoverlay=spi{self.bus}-2cs' to /boot/firmware/config.txt and reboot.")

            self.led_init_state = 0

    def check_spi_state(self): return self.led_init_state

    def spi_gpio_info(self):

        if self.bus == 0:

            print("SPI0-MOSI: GPIO10(WS2812-PIN)  SPI0-MISO: GPIO9  SPI0-SCLK: GPIO11  SPI0-CE0: GPIO8  SPI0-CE1: GPIO7")

        elif self.bus == 1:

            print("SPI1-MOSI: GPIO20(WS2812-PIN)  SPI1-MISO: GPIO19  SPI1-SCLK: GPIO21  SPI1-CE0: GPIO18  SPI1-CE1: GPIO17  SPI0-CE1: GPIO16")

        elif self.bus == 2:

            print("SPI2-MOSI: GPIO41(WS2812-PIN)  SPI2-MISO: GPIO40  SPI2-SCLK: GPIO42  SPI2-CE0: GPIO43  SPI2-CE1: GPIO44  SPI2-CE1: GPIO45")

        elif self.bus == 3:

            print("SPI3-MOSI: GPIO2(WS2812-PIN)   SPI3-MISO: GPIO1   SPI3-SCLK: GPIO3  SPI3-CE0: GPIO0  SPI3-CE1: GPIO24")

        elif self.bus == 4:

            print("SPI4-MOSI: GPIO6(WS2812-PIN)  SPI4-MISO: GPIO5   SPI4-SCLK: GPIO7  SPI4-CE0: GPIO4  SPI4-CE1: GPIO25")

        elif self.bus == 5:

            print("SPI5-MOSI: GPIO14(WS2812-PIN) SPI5-MISO: GPIO13  SPI5-SCLK: GPIO15 SPI5-CE0: GPIO12 SPI5-CE1: GPIO26")

        elif self.bus == 6:

            print("SPI6-MOSI: GPIO20(WS2812-PIN) SPI6-MISO: GPIO19  SPI6-SCLK: GPIO21 SPI6-CE0: GPIO18 SPI6-CE1: GPIO27")

    def led_close(self):

        self.set_all_led_rgb([0,0,0])

        self.spi.close()

    def set_led_count(self, count):

        self.led_count = int(count)

        self.led_color = [0,0,0] * self.led_count

        self.led_original_color = [0,0,0] * self.led_count

    def get_led_count(self): return self.led_count

    def set_led_type(self, rgb_type):

        try:

            led_type = ['RGB','RBG','GRB','GBR','BRG','BGR']

            led_type_offset = [0x06,0x09,0x12,0x21,0x18,0x24]

            index = led_type.index(rgb_type)

            self.led_red_offset   = (led_type_offset[index] >> 4) & 0x03

            self.led_green_offset = (led_type_offset[index] >> 2) & 0x03

            self.led_blue_offset  = (led_type_offset[index] >> 0) & 0x03

            return index

        except ValueError:

            self.led_red_offset   = 1

            self.led_green_offset = 0

            self.led_blue_offset  = 2

            return -1

    def set_led_brightness(self, brightness):

        self.led_brightness = int(brightness)

        for i in range(self.get_led_count()):

            self.set_led_rgb_data(i, self.led_original_color[i*3:(i+1)*3])

    def set_ledpixel(self, index, r, g, b):

        p = [0,0,0]

        p[self.led_red_offset]   = round(int(r) * self.led_brightness / 255)

        p[self.led_green_offset] = round(int(g) * self.led_brightness / 255)

        p[self.led_blue_offset]  = round(int(b) * self.led_brightness / 255)

        self.led_original_color[index*3 + self.led_red_offset]   = int(r)

        self.led_original_color[index*3 + self.led_green_offset] = int(g)

        self.led_original_color[index*3 + self.led_blue_offset]  = int(b)

        for i in range(3):

            self.led_color[index*3 + i] = p[i]

    def set_led_color_data(self, index, r, g, b): self.set_ledpixel(int(index), r, g, b)

    def set_led_rgb_data(self, index, color):     self.set_ledpixel(int(index), int(color[0]), int(color[1]), int(color[2]))

    def set_led_color(self, index, r, g, b):      self.set_ledpixel(int(index), r, g, b); self.show()

    def set_led_rgb(self, index, color):          self.set_led_rgb_data(int(index), color); self.show()

    def set_all_led_color_data(self, r, g, b):

        for i in range(self.get_led_count()):

            self.set_led_color_data(i, r, g, b)

    def set_all_led_rgb_data(self, color):

        for i in range(self.get_led_count()):

            self.set_led_rgb_data(i, color)

    def set_all_led_color(self, r, g, b):

        for i in range(self.get_led_count()):

            self.set_led_color_data(i, r, g, b)

        self.show()

    def set_all_led_rgb(self, color):

        for i in range(self.get_led_count()):

            self.set_led_rgb_data(i, color)

        self.show()

    def write_ws2812_numpy8(self):

        d = numpy.array(self.led_color, dtype=numpy.uint8).ravel()

        tx = numpy.zeros(len(d)*8, dtype=numpy.uint8)

        for ibit in range(8):

            tx[7-ibit::8] = ((d >> ibit) & 1) * 0x78 + 0x80

        if self.led_init_state != 0:

            self.spi.xfer(tx.tolist(), int(8/1.25e-6))  # ~6.4 MHz

    def write_ws2812_numpy4(self):

        d = numpy.array(self.led_color, dtype=numpy.uint8).ravel()

        tx = numpy.zeros(len(d)*4, dtype=numpy.uint8)

        for ibit in range(4):

            tx[3-ibit::4] = ((d >> (2*ibit+1)) & 1) * 0x60 + ((d >> (2*ibit+0)) & 1) * 0x06 + 0x88

        if self.led_init_state != 0:

            self.spi.xfer(tx.tolist(), int(4/1.0e-6))

    def _reset_latch(self):

        if self.led_init_state != 0:

            try:

                self.spi.xfer([0x00]*192, int(8/1.25e-6))  # ~240µs low

            except Exception:

                self.spi.xfer([0x00]*192)

    def show(self, mode=None):

        if mode is None:

            mode = self._get_spi_mode_from_params()

        if mode == 1:

            self.write_ws2812_numpy8()

        else:

            self.write_ws2812_numpy4()

        self._reset_latch()

    def wheel(self, pos):

        if pos < 85:

            return [(255 - pos*3), (pos*3), 0]

        elif pos < 170:

            pos -= 85

            return [0, (255 - pos*3), (pos*3)]

        else:

            pos -= 170

            return [(pos*3), 0, (255 - pos*3)]

    def hsv2rgb(self, h, s, v):

        h = h % 360

        rgb_max = round(v * 2.55)

        rgb_min = round(rgb_max * (100 - s) / 100)

        i = round(h / 60)

        diff = round(h % 60)

        rgb_adj = round((rgb_max - rgb_min) * diff / 60)

        if i == 0:   r,g,b = rgb_max, rgb_min + rgb_adj, rgb_min

        elif i == 1: r,g,b = rgb_max - rgb_adj, rgb_max, rgb_min

        elif i == 2: r,g,b = rgb_min, rgb_max, rgb_min + rgb_adj

        elif i == 3: r,g,b = rgb_min, rgb_max - rgb_adj, rgb_max

        elif i == 4: r,g,b = rgb_min + rgb_adj, rgb_min, rgb_max

        else:        r,g,b = rgb_max, rgb_min, rgb_max - rgb_adj

        return [r,g,b]

if __name__ == '__main__':

    import time, os

    print("spidev version is", spidev.__version__)

    print("spidev devices:"); os.system("ls /dev/spi*")

    led = Freenove_SPI_LedPixel(8, 60, 'GRB')

    try:

        if led.check_spi_state() != 0:

            led.set_led_count(8)

            for _ in range(3):

                for i in range(8):

                    for j in range(8):

                        led.set_led_rgb_data(j, [255,255,255] if j==i else [0,0,0])

                    led.show(); print("lit", i); time.sleep(0.08)

            led.set_all_led_rgb([0,0,0]); led.show()

        else:

            led.led_close()

    except KeyboardInterrupt:

        led.led_close()
