import os
from gpiozero import Button
import time
import subprocess
import threading

BUTTONS = {
    'PLAY_PAUSE': 20,
    'PREV': 16,
    'NEXT': 26,
    'EXECUTE_SCRIPT': 13
}

LONG_PRESS_TIME = 2
DEBOUNCE_TIME = 0.05

def run_command(command):
    try:
        if isinstance(command, str) and command.startswith('/home/pi/'):
            if not os.path.exists(command):
                print(f"Error: The file {command} does not exist.")
                return
            if not os.access(command, os.X_OK):
                print(f"Error: The file {command} does not have execution permission.")
                return
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Exit code: {e.returncode}")
        print(f"Error output: {e.stderr}")

COMMANDS = {
    'PLAY_PAUSE': {
        'short': lambda: run_command('mpc toggle'),
        'long': lambda: [
            run_command('pkill -f roulette.sh'),
            run_command('pkill -f ashuffle'),
            time.sleep(1),
            run_command('mpc stop'),
            run_command('mpc clear'),
            run_command('mpc consume off')
        ]
    },
    'PREV': {
        'short': lambda: run_command('mpc cdprev'),
        'long': lambda: run_command('sudo python3 /home/pi/copy_usb.py')
    },
    'NEXT': {
        'short': lambda: run_command('mpc next'),
        'long': lambda: run_command('sudo systemctl poweroff')
    },
    'EXECUTE_SCRIPT': {
        'short': lambda: run_command('/home/pi/roulette.sh'),
        'long': lambda: [
            run_command('pkill -f roulette.sh'),
            run_command('pkill -f ashuffle'),
            time.sleep(1),
            run_command('mpc stop'),
            run_command('mpc clear'),
            run_command('mpc consume off'),
            run_command('/home/pi/roulette_album.sh')
        ]
    }
}

def execute_command(command):
    if callable(command):
        command()
    elif isinstance(command, list):
        for cmd in command:
            if callable(cmd):
                cmd()

class ButtonHandler:
    def __init__(self, button_name, pin):
        self.button_name = button_name
        self.button = Button(pin, pull_up=True, bounce_time=DEBOUNCE_TIME)
        self.press_start_time = 0
        self.button.when_pressed = self.on_press
        self.button.when_released = self.on_release
        self.long_press_timer = None

    def on_press(self):
        self.press_start_time = time.time()
        self.long_press_timer = threading.Timer(LONG_PRESS_TIME, self.on_long_press)
        self.long_press_timer.start()

    def on_release(self):
        if self.long_press_timer:
            self.long_press_timer.cancel()
        
        if time.time() - self.press_start_time < LONG_PRESS_TIME:
            self.on_short_press()

    def on_short_press(self):
        print(f"Short press detected for {self.button_name}")
        execute_command(COMMANDS[self.button_name]['short'])

    def on_long_press(self):
        print(f"Long press detected for {self.button_name}")
        execute_command(COMMANDS[self.button_name]['long'])

button_handlers = [ButtonHandler(name, pin) for name, pin in BUTTONS.items()]

print("Script started. Press Ctrl+C to exit.")
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Program terminated by user")
