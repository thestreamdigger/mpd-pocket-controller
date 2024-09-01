import os
import shutil
import time
import threading
import psutil
from mpd import MPDClient
from gpiozero import LED

MPD_HOST = os.getenv('MPD_HOST', 'localhost')
MPD_PORT = int(os.getenv('MPD_PORT', 6600))
LED_PIN = 25
MOUNT_POINT = '/mnt/'

def setup_led():
    return LED(LED_PIN)

def led_pattern(led, pattern, stop_event):
    while not stop_event.is_set():
        for duration in pattern:
            if stop_event.is_set():
                break
            led.toggle()
            time.sleep(duration)
    led.off()

def copying_pattern(led, stop_event):
    pattern = [0.2, 0.2]  # Fast blinking
    led_pattern(led, pattern, stop_event)

def error_pattern(led, stop_event):
    pattern = [0.5, 0.5]  # Slow blinking
    led_pattern(led, pattern, stop_event)

def eject_usb(drive):
    try:
        os.system(f'sudo eject {drive}')
    except Exception as e:
        print(f"Failed to eject USB drive: {e}")

def find_usb_drive():
    try:
        mounted_drives = [device.mountpoint for device in psutil.disk_partitions() if device.mountpoint.startswith('/media/')]
        if len(mounted_drives) == 1:
            return mounted_drives[0]
        elif len(mounted_drives) > 1:
            return "Error: Multiple USB drives detected."
        else:
            return None
    except Exception as e:
        print(f"Error finding USB drives: {e}")
        return None

def copy_to_usb(full_path, usb_drive):
    try:
        if not os.path.exists(full_path):
            print(f"Directory not found: {full_path}")
            return False
        path_components = os.path.normpath(full_path).split(os.sep)
        artist_name = path_components[-3] if len(path_components) > 3 else 'UnknownArtist'
        album_name = path_components[-2] if len(path_components) > 3 else 'UnknownAlbum'
        dest_dir = os.path.join(usb_drive, artist_name, album_name)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        album_dir = os.path.join('/', *path_components[:-1])
        if not os.path.exists(album_dir):
            print(f"Album directory not found: {album_dir}")
            return False
        
        for file in os.listdir(album_dir):
            src = os.path.join(album_dir, file)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dest_dir, file))
        return True
    except Exception as e:
        print(f"Error copying files to USB: {e}")
        return False

def main():
    led = setup_led()
    stop_event = threading.Event()
    client = MPDClient()
    try:
        client.connect(MPD_HOST, MPD_PORT)
        song = client.currentsong()
        song_path = song.get('file', '') if song else ''
        if song_path and not song_path.startswith(MOUNT_POINT):
            song_path = os.path.join(MOUNT_POINT, song_path.strip('/'))
        if not os.path.exists(song_path):
            error_pattern(led, threading.Event())
        else:
            usb_drive = find_usb_drive()
            if usb_drive and not usb_drive.startswith("Error"):
                led_thread = threading.Thread(target=copying_pattern, args=(led, stop_event))
                led_thread.start()
                if copy_to_usb(song_path, usb_drive):
                    eject_usb(usb_drive)
                    stop_event.set()
                    led_thread.join()
                else:
                    stop_event.set()
                    led_thread.join()
                    error_pattern(led, threading.Event())
            else:
                print("No USB drive found or multiple drives detected.")
                error_pattern(led, threading.Event())
    except Exception as e:
        print(f"An error occurred: {e}")
        error_pattern(led, threading.Event())
    finally:
        client.close()
        client.disconnect()
        led.off()

if __name__ == '__main__':
    main()