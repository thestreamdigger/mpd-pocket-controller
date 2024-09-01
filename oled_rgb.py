import signal
import sys
import time
from mpd import MPDClient, ConnectionError
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageFont, ImageDraw
from rpi_ws281x import PixelStrip, Color
from pictures import images

MPD_HOST = "localhost"
MPD_PORT = 6600

OLED_WIDTH = 128
OLED_HEIGHT = 64
I2C_PORT = 1
I2C_ADDRESS = 0x3C

FONT_PATH = "/usr/share/fonts/truetype/heavitas/Heavitas.ttf"
TIME_FONT_PATH = "/usr/share/fonts/opentype/acqua/Color Basic.otf"
FONT_SIZE = 22
TIME_FONT_SIZE = 28

LED_PIN = 18
NUM_LEDS = 1
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 127 #255 Max
LED_CHANNEL = 0

AQUA = Color(0, 25, 20)
VIOLET = Color(15, 0, 20)
RED = Color(25, 0, 0)

DISPLAY_DURATION = 20
SCROLL_INTERVAL = 0.02
SCROLL_STEP = 2
SCROLL_SEPARATOR = " >>> "
SCROLL_DELAY = 2

SCREENSAVER_TIMEOUT = 20
SCREENSAVER_IMAGE_DISPLAY_TIME = 5

class RGBLEDController:
    def __init__(self, num_leds, pin, freq_hz, dma, channel, brightness):
        self.strip = PixelStrip(num_leds, pin, freq_hz, dma, channel, brightness, False)
        self.strip.begin()
        self.set_color(Color(0, 0, 0))

    def set_color(self, color):
        self.strip.setPixelColor(0, color)
        self.strip.show()

    def turn_off(self):
        self.set_color(Color(0, 0, 0))

    def update_status(self, status):
        state = status.get('state')
        color_map = {
            'play': AQUA,
            'pause': VIOLET,
            'stop': RED
        }
        self.set_color(color_map.get(state, Color(0, 0, 0)))

class OLEDController:
    def __init__(self, port, address, width, height):
        serial = i2c(port=port, address=address)
        self.device = ssd1306(serial)
        self.width = width
        self.height = height
        self.font = None
        self.time_font = None
        self.scroll_offset = 0

    def load_fonts(self):
        try:
            self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
            self.time_font = ImageFont.truetype(TIME_FONT_PATH, TIME_FONT_SIZE)
        except IOError as e:
            print(f"Error loading fonts: {e}")
            sys.exit(1)

    def draw_text(self, draw, text, position, font=None):
        draw.text(position, text, font=(font or self.font), fill="white")

    def clear(self):
        with canvas(self.device) as draw:
            draw.rectangle(self.device.bounding_box, outline="black", fill="black")

    def display_image(self, image_bytes):
        img = Image.frombytes('1', (self.width, self.height), bytes(image_bytes), 'raw')
        self.device.display(img)

    def display_error(self, line1, line2):
        with canvas(self.device) as draw:
            self.draw_text(draw, line1, (0, 10))
            self.draw_text(draw, line2, (0, 35))

    def get_text_width(self, text):
        return self.font.getbbox(text)[2]

    def scroll_text(self, text, start_time):
        text_with_separator = text + SCROLL_SEPARATOR + text
        text_width = self.get_text_width(text_with_separator)
        
        if text_width <= self.width:
            image = Image.new('1', (self.width, self.height), color=0)
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), text, font=self.font, fill=1)
            return image

        image = Image.new('1', (text_width, self.height), color=0)
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text_with_separator, font=self.font, fill=1)

        if time.time() - start_time < SCROLL_DELAY:
            return image.crop((0, 0, self.width, self.height))

        self.scroll_offset = (self.scroll_offset + SCROLL_STEP) % self.get_text_width(text + SCROLL_SEPARATOR)
        cropped = image.crop((self.scroll_offset, 0, self.scroll_offset + self.width, self.height))
        return cropped

class MPDController:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = self.create_client()

    def create_client(self):
        client = MPDClient()
        client.timeout = 10
        client.idletimeout = None
        client.connect(self.host, self.port)
        return client

    def reconnect(self):
        try:
            self.client.connect(self.host, self.port)
            return True
        except:
            return False

    def get_status(self):
        return self.client.status()

    def get_current_song(self):
        return self.client.currentsong()

    def close(self):
        if self.client:
            self.client.close()

def format_time(seconds):
    minutes, seconds = divmod(int(float(seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"

def update_last_not_playing_time(current_time, last_time):
    return current_time if last_time is None else last_time

def handle_play_state(draw, oled, mpd_controller, status, display_state):
    current_song = mpd_controller.get_current_song()
    track_info = current_song.get('track', "Stream")
    artist = current_song.get('artist', "Unknown Artist")
    title = current_song.get('title', "Unknown Title")

    if display_state['mode'] == 'track':
        display_text = f"Trk. {int(track_info):02d}" if track_info.isdigit() else track_info
        oled.draw_text(draw, display_text, (0, 10))
    elif display_state['mode'] == 'artist':
        scrolled_image = oled.scroll_text(artist, display_state['mode_start_time'])
        draw.bitmap((0, 10), scrolled_image, fill="white")
    else:
        scrolled_image = oled.scroll_text(title, display_state['mode_start_time'])
        draw.bitmap((0, 10), scrolled_image, fill="white")

    elapsed_time = status.get('elapsed', '0')
    oled.draw_text(draw, format_time(elapsed_time), (0, 35), font=oled.time_font)

    current_time = time.time()
    if current_time - display_state['last_change'] >= DISPLAY_DURATION:
        display_state['mode'] = {'track': 'artist', 'artist': 'title', 'title': 'track'}[display_state['mode']]
        display_state['last_change'] = current_time
        display_state['mode_start_time'] = current_time
        oled.scroll_offset = 0

def handle_pause_state(draw, oled, mpd_controller, status):
    oled.draw_text(draw, "Paused", (0, 10))

def handle_stop_state(draw, oled, mpd_controller, status):
    oled.draw_text(draw, "Not", (0, 10))
    oled.draw_text(draw, "Playing", (0, 35))

def update_display(oled, mpd_controller, rgb_led, last_not_playing_time, display_state):
    try:
        status = mpd_controller.get_status()
        state = status['state']
        rgb_led.update_status(status)
        with canvas(oled.device) as draw:
            state_handlers = {
                'play': handle_play_state,
                'pause': handle_pause_state,
                'stop': handle_stop_state
            }
            handler = state_handlers.get(state)
            if handler:
                if state == 'play':
                    handler(draw, oled, mpd_controller, status, display_state)
                else:
                    handler(draw, oled, mpd_controller, status)
            return None if state == 'play' else update_last_not_playing_time(time.time(), last_not_playing_time)
    except ConnectionError:
        if not mpd_controller.reconnect():
            rgb_led.turn_off()
            oled.display_error("MPD", "Offline")
        return update_last_not_playing_time(time.time(), last_not_playing_time)

def display_screensaver(oled, mpd_controller, rgb_led):
    for image_bytes in images.values():
        if mpd_controller.get_status()['state'] == 'play':
            return
        oled.display_image(image_bytes)
        time.sleep(SCREENSAVER_IMAGE_DISPLAY_TIME)

def cleanup(oled, rgb_led, mpd_controller):
    oled.clear()
    rgb_led.turn_off()
    mpd_controller.close()

def signal_handler(sig, frame):
    print(f"Received signal: {sig}")
    cleanup(oled, rgb_led, mpd_controller)
    sys.exit(0)

if __name__ == "__main__":
    oled = OLEDController(I2C_PORT, I2C_ADDRESS, OLED_WIDTH, OLED_HEIGHT)
    rgb_led = RGBLEDController(NUM_LEDS, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_CHANNEL, LED_BRIGHTNESS)
    mpd_controller = MPDController(MPD_HOST, MPD_PORT)
    
    oled.load_fonts()
    
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
        signal.signal(sig, signal_handler)
    
    try:
        with canvas(oled.device) as draw:
            oled.draw_text(draw, "V2.BS", (20, 20))
        time.sleep(2)
        
        last_not_playing_time = None
        display_state = {'mode': 'track', 'last_change': time.time(), 'mode_start_time': time.time()}
        
        while True:
            last_not_playing_time = update_display(oled, mpd_controller, rgb_led, last_not_playing_time, display_state)
            if last_not_playing_time and (time.time() - last_not_playing_time) >= SCREENSAVER_TIMEOUT:
                display_screensaver(oled, mpd_controller, rgb_led)
                last_not_playing_time = None
            time.sleep(SCROLL_INTERVAL)
    except Exception as e:
        print(f"Unhandled error: {e}")
    finally:
        cleanup(oled, rgb_led, mpd_controller)
