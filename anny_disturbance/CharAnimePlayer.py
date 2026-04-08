#!/usr/bin/python
import pickle
import os
import time
import platform
import sys
import select
import termios
import tty


def key_pressed():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.read(1)
    return None

# this is a random ascii player I found
class CharAnimePlayer:
    def __init__(self, mode, filepath, fps, show_width, show_height):
        sysstr = platform.system()
        if sysstr == "Windows":
            self.clear_command = "cls"
        elif sysstr == "Linux":
            self.clear_command = "clear"
        else:
            print("unknown platform: ", sysstr)
            sys.exit(0)

        self.show_height = show_height
        self.show_width = show_width
        self.mode = mode
        self.filepath = filepath
        self.sleep_slot = 1 / fps
        self.ctrl_c_count = 0  # 🔥 persistent counter

    def play_frames(self):
        for frame in self.frame_list:
            os.system(self.clear_command)
            print(frame)
            time.sleep(self.sleep_slot)
        os.system(self.clear_command)

    def play_raw(self, show_width, show_height):
        import cv2

        self.ascii_char = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        self.char_len = len(self.ascii_char)

        vc = cv2.VideoCapture(self.filepath)
        if vc.isOpened():
            rval, frame = vc.read()
        else:
            print('open failed! Abort.')
            exit(1)

        # Setup keyboard capture
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)

        try:
            while rval:
                # Ctrl+L immediate kill
                key = key_pressed()
                if key == '\x0c':  # Ctrl+L
                    print("\n[+] Ctrl+L pressed. Exiting immediately.")
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (show_width, show_height))

                text = ""
                for pixel_line in gray:
                    for pixel in pixel_line:
                        text += self.ascii_char[int(pixel / 256 * self.char_len)]
                    text += "\n"

                os.system(self.clear_command)
                print(text)
                time.sleep(self.sleep_slot)

                rval, frame = vc.read()

            os.system(self.clear_command)
            print("play finished.")

        except KeyboardInterrupt:
            # 🔥 Ctrl+C counter logic
            self.ctrl_c_count += 1
            if self.ctrl_c_count < 300: # after 300 crtl + c it works
                # restart playback
                self.play_raw(show_width, show_height)
            else:
                print("\n[+] Exiting after 10 Ctrl+C presses.")
                os.system(self.clear_command)

        finally:
            # 🔥 restore terminal properly
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def newFramesPlayer(filepath, fps):
    return CharAnimePlayer("charsFrames", filepath, fps, -1, -1)


def newRawPlayer(filepath, fps, show_width, show_height):
    return CharAnimePlayer('rawVideo', filepath, fps, show_width, show_height)


def printHelp():
    print("Help:")
    print("\tUsage: python charAnimePlayer.py <file> [option]")
    print("\tOption:")
    print("\t\t-help \t\tshow help")
    print("\t\t-w -width \tspecify width")
    print("\t\t-h -height \tspecify height")
    print("\t\t-f -fps \tspecify fps from 1 to 60")
    print("\t\t--raw \t\traw play mode")
    print("\tExample:")
    print("\t\tpython charAnimePlayer.py bad-apple.mp4 -fps 60 -width 120 -height 35 --raw")
    print("\t\tpython charAnimePlayer.py file.dat -fps 60")


if __name__ == "__main__":
    argv = sys.argv
    i = 1

    filepath = ""
    width = -1
    height = -1
    fps = -1
    player_type = "frames"
    player = None

    while i < len(argv):
        if argv[i].lower() == "-help":
            printHelp()
            sys.exit(0)
        elif argv[i].lower() == "--raw":
            player_type = "raw"
        elif argv[i].lower() == "-w" or argv[i].lower() == "-width":
            if i + 1 < len(argv):
                width = int(argv[i + 1])
                i += 1
        elif argv[i].lower() == "-h" or argv[i].lower() == "-height":
            if i + 1 < len(argv):
                height = int(argv[i + 1])
                i += 1
        elif argv[i].lower() == "-f" or argv[i].lower() == "-fps":
            if i + 1 < len(argv):
                fps = int(argv[i + 1])
                i += 1
        else:
            filepath = argv[i]
        i += 1

    if player_type == "frames":
        if filepath == "" or fps < 0:
            printHelp()
            sys.exit(0)
    elif player_type == "raw":
        if filepath == "" or fps < 0 or width < 0 or height < 0:
            printHelp()
            sys.exit(0)

    if player_type == "raw":
        player = newRawPlayer(filepath, fps, width, height)
        player.play_raw(width, height)
    else:
        player = newFramesPlayer(filepath, fps)
        player.play_frames()