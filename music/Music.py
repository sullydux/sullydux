#!/usr/bin/env python3
"""
Run in Terminal with:
python3 ~/Desktop/Media/Music/Music.py
"""

import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from AVFoundation import AVAudioPlayer, AVURLAsset
from Foundation import NSURL


MUSIC_DIR = Path.home() / "Desktop" / "Coding" / "Github" / "sullydux" / "Music"
CATALOG_PATH = MUSIC_DIR / "music.json"
SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".aiff", ".flac", ".caf"}
WINDOW_BG = "#0b0f14"
PANEL_BG = "#121821"
PANEL_ALT = "#18212c"
ACCENT = "#59c9a5"
ACCENT_ACTIVE = "#76ddb9"
TEXT_MAIN = "#f5f7fa"
TEXT_MUTED = "#97a6b5"
BORDER = "#263241"
LIST_BG = "#0f141c"


def format_time(seconds: float) -> str:
    if seconds is None or math.isnan(seconds) or seconds < 0:
        seconds = 0
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def duration_for_file(path: Path) -> float:
    url = NSURL.fileURLWithPath_(str(path))
    asset = AVURLAsset.URLAssetWithURL_options_(url, None)
    duration = asset.duration()
    if not duration.timescale:
        return 0.0
    return max(0.0, float(duration.value) / float(duration.timescale))


def build_catalog() -> list[dict]:
    tracks = []
    for path in sorted(MUSIC_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.name in {"music.json", "Music.py"} or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        stat = path.stat()
        tracks.append(
            {
                "name": path.stem,
                "filename": path.name,
                "path": str(path),
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_timestamp": int(stat.st_mtime),
                "duration_seconds": round(duration_for_file(path), 3),
            }
        )

    with CATALOG_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"music_folder": str(MUSIC_DIR), "track_count": len(tracks), "tracks": tracks}, handle, indent=2)

    return tracks


class MusicPlayerApp:
    def __init__(self, root: tk.Tk, tracks: list[dict]) -> None:
        self.root = root
        self.tracks = tracks
        self.index = 0
        self.player = None
        self.is_seeking = False
        self.was_playing_before_seek = False
        self.last_known_duration = 0.0
        self.compact_mode = False

        self.track_title = tk.StringVar(value="No song loaded")
        self.track_meta = tk.StringVar(value="Ready")
        self.time_value = tk.DoubleVar(value=0.0)
        self.elapsed_label = tk.StringVar(value="0:00")
        self.remaining_label = tk.StringVar(value="-0:00")
        self.volume_value = tk.DoubleVar(value=0.85)

        self.configure_window()
        self.build_ui()

        if self.tracks:
            self.load_track(0, autoplay=False)
        self.root.after(250, self.refresh_ui)

    def configure_window(self) -> None:
        self.root.title("Music Player")
        self.root.geometry("920x560")
        self.root.minsize(820, 500)
        self.root.configure(bg=WINDOW_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Player.TFrame", background=WINDOW_BG)
        style.configure("Panel.TFrame", background=PANEL_BG, relief="flat")
        style.configure("PanelAlt.TFrame", background=PANEL_ALT, relief="flat")
        style.configure("Player.TLabel", background=WINDOW_BG, foreground=TEXT_MAIN)
        style.configure("Panel.TLabel", background=PANEL_BG, foreground=TEXT_MAIN)
        style.configure("PanelAlt.TLabel", background=PANEL_ALT, foreground=TEXT_MAIN)
        style.configure("Muted.TLabel", background=WINDOW_BG, foreground=TEXT_MUTED)
        style.configure("MutedPanel.TLabel", background=PANEL_BG, foreground=TEXT_MUTED)
        style.configure("MutedAlt.TLabel", background=PANEL_ALT, foreground=TEXT_MUTED)
        style.configure(
            "Player.TButton",
            padding=(16, 10),
            font=("Helvetica", 13, "bold"),
            background=PANEL_ALT,
            foreground=TEXT_MAIN,
            borderwidth=0,
            focuscolor=PANEL_ALT,
        )
        style.map(
            "Player.TButton",
            background=[("active", ACCENT), ("pressed", ACCENT_ACTIVE)],
            foreground=[("active", "#06110d"), ("pressed", "#06110d")],
        )

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="Player.TFrame", padding=22)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=3)
        outer.columnconfigure(1, weight=2)
        outer.rowconfigure(0, weight=1)
        self.outer = outer

        player_frame = ttk.Frame(outer, style="Panel.TFrame", padding=26)
        player_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        player_frame.columnconfigure(0, weight=1)
        self.player_frame = player_frame

        header_row = ttk.Frame(player_frame, style="Panel.TFrame")
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(0, weight=1)

        ttk.Label(
            header_row,
            text="Now Playing",
            style="MutedPanel.TLabel",
            font=("Helvetica", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.compact_button = ttk.Button(
            header_row,
            text="Compact Mode",
            command=self.toggle_compact_mode,
            style="Player.TButton",
        )
        self.compact_button.grid(row=0, column=1, sticky="e")

        ttk.Label(
            player_frame,
            textvariable=self.track_title,
            style="Panel.TLabel",
            font=("Helvetica", 28, "bold"),
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(18, 8))

        self.track_meta_label = ttk.Label(
            player_frame,
            textvariable=self.track_meta,
            style="MutedPanel.TLabel",
            font=("Helvetica", 12),
        )
        self.track_meta_label.grid(row=2, column=0, sticky="w", pady=(0, 26))

        self.progress = tk.Scale(
            player_frame,
            variable=self.time_value,
            orient="horizontal",
            from_=0,
            to=1,
            resolution=0.1,
            showvalue=False,
            troughcolor="#1f2935",
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            bg=PANEL_BG,
            fg=TEXT_MAIN,
            length=560,
            sliderlength=18,
            width=20,
        )
        self.progress.grid(row=3, column=0, sticky="ew")
        self.progress.bind("<ButtonPress-1>", self.begin_seek)
        self.progress.bind("<ButtonRelease-1>", self.finish_seek)

        time_row = ttk.Frame(player_frame, style="Panel.TFrame")
        time_row.grid(row=4, column=0, sticky="ew", pady=(10, 32))
        time_row.columnconfigure(0, weight=1)
        time_row.columnconfigure(1, weight=1)

        ttk.Label(time_row, textvariable=self.elapsed_label, style="MutedPanel.TLabel", font=("Helvetica", 12)).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(time_row, textvariable=self.remaining_label, style="MutedPanel.TLabel", font=("Helvetica", 12)).grid(
            row=0, column=1, sticky="e"
        )

        controls = ttk.Frame(player_frame, style="Panel.TFrame")
        controls.grid(row=5, column=0, sticky="w")
        self.controls = controls

        self.previous_button = ttk.Button(controls, text="Previous", command=self.previous_track, style="Player.TButton")
        self.previous_button.grid(row=0, column=0, padx=(0, 10))

        self.play_button = ttk.Button(controls, text="Play", command=self.toggle_play_pause, style="Player.TButton")
        self.play_button.grid(row=0, column=1, padx=10)

        self.next_button = ttk.Button(controls, text="Next", command=self.next_track, style="Player.TButton")
        self.next_button.grid(row=0, column=2, padx=(10, 0))

        volume_row = ttk.Frame(player_frame, style="PanelAlt.TFrame", padding=16)
        volume_row.grid(row=6, column=0, sticky="ew", pady=(28, 0))
        volume_row.columnconfigure(1, weight=1)
        self.volume_row = volume_row

        ttk.Label(volume_row, text="Volume", style="MutedAlt.TLabel", font=("Helvetica", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 14)
        )
        self.volume_slider = tk.Scale(
            volume_row,
            variable=self.volume_value,
            orient="horizontal",
            from_=0,
            to=1,
            resolution=0.01,
            showvalue=False,
            troughcolor="#243243",
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            bg=PANEL_ALT,
            fg=TEXT_MAIN,
            length=320,
            sliderlength=18,
            width=18,
            command=self.on_volume_change,
        )
        self.volume_slider.grid(row=0, column=1, sticky="ew")

        playlist_frame = ttk.Frame(outer, style="PanelAlt.TFrame", padding=22)
        playlist_frame.grid(row=0, column=1, sticky="nsew")
        playlist_frame.columnconfigure(0, weight=1)
        playlist_frame.rowconfigure(1, weight=1)
        self.playlist_frame = playlist_frame

        ttk.Label(
            playlist_frame,
            text="Library",
            style="MutedAlt.TLabel",
            font=("Helvetica", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.playlist = tk.Listbox(
            playlist_frame,
            activestyle="none",
            bg=LIST_BG,
            fg=TEXT_MAIN,
            highlightthickness=1,
            highlightbackground=BORDER,
            selectbackground=ACCENT,
            selectforeground="#06110d",
            font=("Helvetica", 13),
            borderwidth=0,
            relief="flat",
        )
        self.playlist.grid(row=1, column=0, sticky="nsew")
        self.playlist.bind("<Double-Button-1>", self.play_selected_track)
        self.playlist.bind("<Return>", self.play_selected_track)

        for track in self.tracks:
            self.playlist.insert("end", track["filename"])

        if self.tracks:
            self.playlist.selection_set(0)
            self.playlist.activate(0)

    def toggle_compact_mode(self) -> None:
        self.compact_mode = not self.compact_mode

        if self.compact_mode:
            self.playlist_frame.grid_remove()
            self.track_meta_label.grid_remove()
            self.play_button.grid_remove()
            self.root.geometry("560x250")
            self.root.minsize(520, 230)
            self.compact_button.configure(text="Full Mode")
        else:
            self.playlist_frame.grid()
            self.track_meta_label.grid()
            self.play_button.grid()
            self.root.geometry("920x560")
            self.root.minsize(820, 500)
            self.compact_button.configure(text="Compact Mode")

    def begin_seek(self, _event=None) -> None:
        if not self.player:
            return
        self.is_seeking = True
        self.was_playing_before_seek = bool(self.player.isPlaying())

    def finish_seek(self, _event=None) -> None:
        if not self.player:
            self.is_seeking = False
            return

        duration = self.player.duration()
        target = min(max(self.time_value.get(), 0.0), duration)
        self.player.setCurrentTime_(target)
        self.elapsed_label.set(format_time(target))
        self.remaining_label.set(f"-{format_time(max(duration - target, 0.0))}")
        self.is_seeking = False

        if self.was_playing_before_seek:
            self.player.play()

    def on_volume_change(self, _value=None) -> None:
        if self.player:
            self.player.setVolume_(self.volume_value.get())

    def play_selected_track(self, _event=None) -> None:
        selection = self.playlist.curselection()
        if not selection:
            return
        self.load_track(selection[0], autoplay=True)

    def create_player(self, path: Path):
        url = NSURL.fileURLWithPath_(str(path))
        player, error = AVAudioPlayer.alloc().initWithContentsOfURL_error_(url, None)
        if player is None:
            raise RuntimeError(str(error) if error else f"Could not open {path.name}")
        player.prepareToPlay()
        player.setVolume_(self.volume_value.get())
        return player

    def load_track(self, index: int, autoplay: bool) -> None:
        self.index = index % len(self.tracks)
        track = self.tracks[self.index]

        if self.player:
            self.player.stop()

        self.player = self.create_player(Path(track["path"]))
        duration = self.player.duration()
        self.last_known_duration = duration
        self.track_title.set(track["filename"])
        self.track_meta.set(f"{track['extension'].upper().replace('.', '')}  •  {format_time(duration)}  •  Looping")
        self.time_value.set(0.0)
        self.progress.configure(to=max(duration, 1.0))
        self.elapsed_label.set("0:00")
        self.remaining_label.set(f"-{format_time(duration)}")
        self.playlist.selection_clear(0, "end")
        self.playlist.selection_set(self.index)
        self.playlist.activate(self.index)
        self.playlist.see(self.index)

        if autoplay:
            self.player.play()
            self.play_button.configure(text="Pause")
        else:
            self.play_button.configure(text="Play")

    def toggle_play_pause(self) -> None:
        if not self.player:
            return
        if self.player.isPlaying():
            self.player.pause()
            self.play_button.configure(text="Play")
        else:
            self.player.play()
            self.play_button.configure(text="Pause")

    def next_track(self) -> None:
        if not self.tracks:
            return
        self.load_track(self.index + 1, autoplay=True)

    def previous_track(self) -> None:
        if not self.tracks:
            return

        current_time = self.player.currentTime() if self.player else 0.0
        if current_time > 3:
            self.player.setCurrentTime_(0.0)
            return

        self.load_track(self.index - 1, autoplay=True)

    def refresh_ui(self) -> None:
        if self.player:
            duration = max(self.player.duration(), 0.0)
            self.last_known_duration = duration or self.last_known_duration
            current = min(max(self.player.currentTime(), 0.0), duration)

            if not self.is_seeking:
                self.time_value.set(current)
                self.elapsed_label.set(format_time(current))
                self.remaining_label.set(f"-{format_time(max(duration - current, 0.0))}")

            near_end = duration > 0 and current >= max(duration - 0.12, 0)
            if near_end and self.player.isPlaying():
                self.player.setCurrentTime_(0.0)
                self.time_value.set(0.0)
                self.elapsed_label.set("0:00")
                self.remaining_label.set(f"-{format_time(self.last_known_duration)}")

            self.play_button.configure(text="Pause" if self.player.isPlaying() else "Play")

        self.root.after(250, self.refresh_ui)

    def close(self) -> None:
        if self.player:
            self.player.stop()
        self.root.destroy()


def main() -> None:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    tracks = build_catalog()

    if not tracks:
        messagebox.showinfo("Music Player", f"No supported audio files found in {MUSIC_DIR}")
        return

    root = tk.Tk()
    MusicPlayerApp(root, tracks)
    root.mainloop()


if __name__ == "__main__":
    main()
