#Pydroid run kivy

import os
import sys
import io
import time
import threading
import shutil
import requests
import yt_dlp
import json
import platform

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.audio import SoundLoader
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.progressbar import MDProgressBar
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

from kivymd.app import MDApp
from kivymd.uix.button import MDIconButton, MDFillRoundFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.card import MDCard
from kivymd.uix.list import OneLineAvatarIconListItem, IconLeftWidget

from io import BytesIO

# Pygame is optional - import lazily to avoid crashes when not installed
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None
    PYGAME_AVAILABLE = False


# ------------------- Environment Detection & Debugging -------------------
class EnvironmentDetector:
    """Detects and configures the app for Mobile (PyDroid 3) vs Desktop environments"""

    def __init__(self):
        self.is_mobile = False
        self.is_pydroid3 = False
        self.is_android = False
        self.platform_name = ""
        self.debug_info = []
        self.pygame_available = False
        self.pygame_codecs = []
        self.ffmpeg_available = False
        self.ffmpeg_path = None
        self.audio_mode = "unknown"

        self._detect_environment()
        self._check_audio_capabilities()

    def _detect_environment(self):
        """Detect the runtime environment"""
        self.debug_info.append("=== ENVIRONMENT DETECTION ===")

        # Check platform
        self.platform_name = platform.system()
        self.debug_info.append(f"Platform: {self.platform_name}")
        self.debug_info.append(f"Python: {platform.python_version()}")

        # Check for PyDroid 3 indicators
        pydroid3_paths = [
            '/data/data/ru.iiec.pydroid3',
            '/data/data/ru.iiec.pydroid3/files',
        ]

        for path in pydroid3_paths:
            if os.path.exists(path):
                self.is_pydroid3 = True
                self.is_mobile = True
                self.is_android = True
                self.debug_info.append(f"✓ PyDroid 3 detected: {path}")
                break

        # Check for Android indicators
        if not self.is_android:
            android_indicators = [
                '/system/build.prop',
                '/sdcard',
                '/storage/emulated/0'
            ]
            for indicator in android_indicators:
                if os.path.exists(indicator):
                    self.is_android = True
                    self.is_mobile = True
                    self.debug_info.append(f"✓ Android detected: {indicator}")
                    break

        # Check environment variables
        if 'ANDROID_ROOT' in os.environ:
            self.is_android = True
            self.is_mobile = True
            self.debug_info.append(f"✓ Android detected via ANDROID_ROOT: {os.environ.get('ANDROID_ROOT')}")

        # Determine mode
        if self.is_pydroid3:
            self.audio_mode = "mobile_pydroid3"
            self.debug_info.append("MODE: Mobile (PyDroid 3)")
        elif self.is_android:
            self.audio_mode = "mobile_android"
            self.debug_info.append("MODE: Mobile (Android)")
        else:
            self.audio_mode = "desktop"
            self.debug_info.append("MODE: Desktop")

        # Check storage paths
        self.debug_info.append("\n=== STORAGE PATHS ===")
        self.debug_info.append(f"Current Dir: {os.getcwd()}")
        self.debug_info.append(f"Home Dir: {os.path.expanduser('~')}")

        # Check writable directories
        test_paths = [
            ".",
            "/storage/emulated/0/Music",
            "/storage/emulated/0/Download",
            os.path.expanduser("~")
        ]

        for test_path in test_paths:
            if os.path.exists(test_path):
                writable = os.access(test_path, os.W_OK)
                self.debug_info.append(f"{'✓' if writable else '✗'} {test_path}: {'writable' if writable else 'read-only'}")

    def _check_audio_capabilities(self):
        """Check pygame and audio codec support"""
        self.debug_info.append("\n=== AUDIO CAPABILITIES ===")

        # Check pygame
        try:
            global pygame
            if pygame is None:
                import pygame as pg
                pygame = pg
            self.pygame_available = True
            self.debug_info.append(f"✓ Pygame version: {pygame.version.ver}")

            # Try to initialize pygame mixer
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

                init_params = pygame.mixer.get_init()
                if init_params:
                    self.debug_info.append(f"✓ Pygame mixer initialized: {init_params}")

                    # Check supported formats (this is indirect)
                    self.debug_info.append("Supported formats: MP3, OGG (typically)")

                    # On Android, pygame has limited codec support
                    if self.is_android:
                        self.debug_info.append("⚠ Android: Limited codec support (MP3 recommended)")
                        self.pygame_codecs = ['mp3', 'ogg']
                    else:
                        self.pygame_codecs = ['mp3', 'ogg', 'wav', 'flac']
                else:
                    self.debug_info.append("✗ Pygame mixer initialization failed")
            except Exception as e:
                self.debug_info.append(f"✗ Pygame mixer error: {e}")
        except ImportError:
            self.debug_info.append("✗ Pygame not available")

        # Check ffmpeg
        self.debug_info.append("\n=== FFMPEG DETECTION ===")
        import subprocess

        ffmpeg_paths = [
            'ffmpeg',
            '/data/data/ru.iiec.pydroid3/files/ffmpeg',
            '/data/data/ru.iiec.pydroid3/files/aarch64-linux-android/bin/ffmpeg',
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/storage/emulated/0/Download/ffmpeg',
        ]

        for ffmpeg_path in ffmpeg_paths:
            try:
                result = subprocess.run(
                    [ffmpeg_path, '-version'],
                    capture_output=True,
                    timeout=3,
                    text=True
                )
                if result.returncode == 0:
                    self.ffmpeg_available = True
                    self.ffmpeg_path = ffmpeg_path
                    version_line = result.stdout.split('\n')[0] if result.stdout else "unknown"
                    self.debug_info.append(f"✓ FFmpeg found: {ffmpeg_path}")
                    self.debug_info.append(f"  Version: {version_line}")
                    break
            except Exception as e:
                continue

        if not self.ffmpeg_available:
            self.debug_info.append("✗ FFmpeg not found")
            if self.is_pydroid3:
                self.debug_info.append("  Install via: pip install ffmpeg-python")
                self.debug_info.append("  Or manually download ffmpeg binary for Android")

        # Check pydub
        try:
            from pydub import AudioSegment
            self.debug_info.append("✓ Pydub available")
        except ImportError:
            self.debug_info.append("✗ Pydub not available")

        # Summary
        self.debug_info.append("\n=== RECOMMENDATIONS ===")
        if self.is_mobile and not self.ffmpeg_available:
            self.debug_info.append("⚠ Mobile mode WITHOUT ffmpeg:")
            self.debug_info.append("  - Download audio as MP3/OGG format (Pygame compatible)")
            self.debug_info.append("  - Pygame player supports MP3 and OGG on Android")
            self.debug_info.append("  - Avoiding M4A/Opus as they may not play without ffmpeg")
        elif self.is_mobile and self.ffmpeg_available:
            self.debug_info.append("✓ Mobile mode WITH ffmpeg:")
            self.debug_info.append("  - Can download any format")
            self.debug_info.append("  - Will auto-convert to MP3 if needed")
        else:
            self.debug_info.append("✓ Desktop mode:")
            self.debug_info.append("  - All features available")

    def get_optimal_audio_format(self):
        """Get the optimal audio format for this environment"""
        if self.is_mobile and not self.ffmpeg_available:
            return 'mp3'
        elif self.is_mobile:
            return 'mp3'
        else:
            return 'bestaudio'

    def get_download_options(self):
        """Get yt-dlp options optimized for this environment"""
        base_options = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }

        if self.is_mobile and not self.ffmpeg_available:
            base_options['format'] = 'bestaudio[ext=mp3]/bestaudio[acodec=mp3]/bestaudio[ext=ogg]/bestaudio[acodec=vorbis]/worst[ext=mp3]/worst[acodec=mp3]/worst[ext=ogg]/worst[acodec=vorbis]'
            base_options['prefer_free_formats'] = True
            self.debug_info.append("Using MP3/OGG container formats only for mobile (Pygame compatible - no ffmpeg)")
            self.debug_info.append("  Note: Avoiding WebM/M4A/Opus - only MP3 and OGG containers work on Pydroid 3")
        elif self.ffmpeg_available:
            base_options['format'] = 'bestaudio/best'
            base_options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            self.debug_info.append("Using best audio with ffmpeg conversion to MP3")
        else:
            base_options['format'] = 'bestaudio/best'

        return base_options

    def print_debug_info(self):
        """Print all debug information"""
        return "\n".join(self.debug_info)

    def get_status_summary(self):
        """Get a short status summary"""
        status = []
        status.append(f"Mode: {self.audio_mode.upper()}")
        status.append(f"Pygame: {'✓' if self.pygame_available else '✗'}")
        status.append(f"FFmpeg: {'✓' if self.ffmpeg_available else '✗'}")
        status.append(f"Optimal Format: {self.get_optimal_audio_format().upper()}")
        return " | ".join(status)

# ------------------- Wake Lock Manager (for Background Playback on Android) -------------------
class WakeLockManager:
    """Manages Android wake locks to enable background audio playback on mobile devices"""

    def __init__(self, is_android=False):
        self.is_android = is_android
        self.wake_lock = None
        self.wake_lock_held = False
        self.pyjnius_available = False

        if self.is_android:
            self._setup_wake_lock()

    def _setup_wake_lock(self):
        """Initialize wake lock using pyjnius"""
        try:
            from jnius import autoclass
            self.pyjnius_available = True

            # Get Android Java classes
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            PowerManager = autoclass('android.os.PowerManager')

            # Get current activity
            activity = PythonActivity.mActivity

            # Create PowerManager instance
            pm = activity.getSystemService(Context.POWER_SERVICE)

            # Create PARTIAL_WAKE_LOCK (keeps CPU running, allows screen to sleep)
            self.wake_lock = pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "MusicPlayer::BackgroundPlayback"
            )

            # Set not reference counted for manual control
            self.wake_lock.setReferenceCounted(False)

            print("✓ Wake lock initialized for background playback")

        except ImportError:
            print("⚠️ pyjnius not available - background playback limited")
            print("  Install pyjnius in Pydroid 3: pip install pyjnius")
        except Exception as e:
            print(f"⚠️ Failed to setup wake lock: {e}")

    def acquire(self):
        """Acquire wake lock to keep CPU running during playback"""
        if not self.is_android or not self.wake_lock:
            return False

        try:
            if not self.wake_lock_held and not self.wake_lock.isHeld():
                self.wake_lock.acquire()
                self.wake_lock_held = True
                print("🔒 Wake lock acquired - music will play in background")
                return True
        except Exception as e:
            print(f"⚠️ Failed to acquire wake lock: {e}")

        return False

    def release(self):
        """Release wake lock to save battery"""
        if not self.is_android or not self.wake_lock:
            return False

        try:
            if self.wake_lock_held and self.wake_lock.isHeld():
                self.wake_lock.release()
                self.wake_lock_held = False
                print("🔓 Wake lock released - battery saver active")
                return True
        except Exception as e:
            print(f"⚠️ Failed to release wake lock: {e}")

        return False

    def is_held(self):
        """Check if wake lock is currently held"""
        if not self.is_android or not self.wake_lock:
            return False

        try:
            return self.wake_lock.isHeld()
        except:
            return False

    def __del__(self):
        """Cleanup: release wake lock on object destruction"""
        self.release()

# ------------------- Pygame Audio Player (Fallback for Pydroid 3) -------------------
class PygameAudioPlayer:
    """Pygame-based audio player as fallback for formats Kivy can't handle"""

    def __init__(self, is_mobile=False, is_android=False):
        self.initialized = False
        self.current_file = None
        self._state = 'stop'
        self._length = 0
        self._position = 0
        self._paused_position = 0
        self.is_mobile = is_mobile
        self.wake_lock_manager = WakeLockManager(is_android=is_android)
        self._init_pygame()

    def _init_pygame(self):
        """Initialize pygame mixer with mobile-optimized settings"""
        global pygame
        try:
            if pygame is None:
                import pygame as pg
                pygame = pg

            if not pygame.mixer.get_init():
                if self.is_mobile:
                    pygame.mixer.init(
                        frequency=44100,
                        size=-16,
                        channels=2,
                        buffer=4096
                    )
                else:
                    pygame.mixer.init(
                        frequency=44100,
                        size=-16,
                        channels=2,
                        buffer=2048
                    )
            self.initialized = True
            print(f"Pygame mixer initialized (mobile={self.is_mobile}): {pygame.mixer.get_init()}")
        except ImportError:
            print("Pygame not installed - audio fallback unavailable")
            self.initialized = False
        except Exception as e:
            print(f"Failed to initialize pygame mixer: {e}")
            self.initialized = False

    def load(self, filepath):
        """Load an audio file"""
        if not self.initialized:
            return False

        try:
            pygame.mixer.music.load(filepath)
            self.current_file = filepath
            # Try to get length using mutagen
            try:
                from mutagen import File
                audio = File(filepath)
                if audio and hasattr(audio.info, 'length'):
                    self._length = audio.info.length
                else:
                    self._length = 0
            except Exception:
                self._length = 0
            return True
        except Exception as e:
            print(f"Pygame failed to load {filepath}: {e}")
            return False

    def play(self):
        """Play the loaded audio"""
        if not self.initialized or not self.current_file:
            return False

        try:
            # Acquire wake lock for background playback
            self.wake_lock_manager.acquire()

            if self._paused_position > 0:
                # Resume from paused position
                pygame.mixer.music.play(start=self._paused_position)
                self._paused_position = 0
            else:
                pygame.mixer.music.play()
            self._state = 'play'
            return True
        except Exception as e:
            print(f"Pygame play error: {e}")
            return False

    def stop(self):
        """Stop playback"""
        if not self.initialized:
            return

        try:
            pygame.mixer.music.stop()
            self._state = 'stop'
            self._paused_position = 0
            # Release wake lock when stopped
            self.wake_lock_manager.release()
        except Exception:
            pass

    def pause(self):
        """Pause playback"""
        if not self.initialized:
            return

        try:
            # Save current position
            self._paused_position = pygame.mixer.music.get_pos() / 1000.0
            pygame.mixer.music.pause()
            self._state = 'pause'
            # Release wake lock when paused to save battery
            self.wake_lock_manager.release()
        except Exception:
            pass

    def unpause(self):
        """Resume playback"""
        if not self.initialized:
            return

        try:
            # Re-acquire wake lock when resuming
            self.wake_lock_manager.acquire()
            pygame.mixer.music.unpause()
            self._state = 'play'
        except Exception:
            pass

    def get_pos(self):
        """Get current playback position in seconds"""
        if not self.initialized or self._state != 'play':
            return self._paused_position

        try:
            pos = pygame.mixer.music.get_pos() / 1000.0  # Convert ms to seconds
            return pos
        except Exception:
            return 0

    def seek(self, position):
        """Seek to position in seconds"""
        if not self.initialized or not self.current_file:
            return

        try:
            # pygame.mixer.music doesn't support seeking on all platforms
            # Best we can do is restart and play from position
            was_playing = self._state == 'play'
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=position)
            if not was_playing:
                pygame.mixer.music.pause()
                self._state = 'pause'
        except Exception as e:
            print(f"Pygame seek error: {e}")

    def unload(self):
        """Unload the current audio"""
        if not self.initialized:
            return

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.current_file = None
            self._state = 'stop'
            self._length = 0
            self._paused_position = 0
        except Exception:
            pass

    @property
    def state(self):
        """Get current playback state"""
        if not self.initialized:
            return 'stop'

        try:
            if pygame.mixer.music.get_busy():
                return 'play'
            elif self._state == 'pause':
                return 'pause'
            else:
                return 'stop'
        except Exception:
            return self._state

    @property
    def length(self):
        """Get audio length in seconds"""
        return self._length

    @property
    def volume(self):
        """Get current volume (0.0 to 1.0)"""
        if not self.initialized:
            return 1.0
        try:
            return pygame.mixer.music.get_volume()
        except Exception:
            return 1.0

    @volume.setter
    def volume(self, value):
        """Set volume (0.0 to 1.0)"""
        if not self.initialized:
            return
        try:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, value)))
        except Exception:
            pass


# ------------------- Audio Converter Module -------------------
class AudioConverter:
    """Handles audio format conversion with fallback support"""

    def __init__(self, env_detector=None):
        self.has_pydub = False
        self.has_ffmpeg = False
        self.env_detector = env_detector
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if pydub and ffmpeg are available"""
        try:
            from pydub import AudioSegment
            self.has_pydub = True

            if self.env_detector and self.env_detector.ffmpeg_available:
                self.has_ffmpeg = True
                self.ffmpeg_path = self.env_detector.ffmpeg_path
                AudioSegment.converter = self.ffmpeg_path
                print(f"Using ffmpeg from environment detector: {self.ffmpeg_path}")
            else:
                import subprocess
                ffmpeg_paths = [
                    'ffmpeg',
                    '/data/data/ru.iiec.pydroid3/files/ffmpeg',
                    '/data/data/ru.iiec.pydroid3/files/aarch64-linux-android/bin/ffmpeg',
                    '/storage/emulated/0/Download/ffmpeg',
                ]

                for ffmpeg_path in ffmpeg_paths:
                    try:
                        result = subprocess.run([ffmpeg_path, '-version'],
                                               capture_output=True,
                                               timeout=2)
                        if result.returncode == 0:
                            self.has_ffmpeg = True
                            self.ffmpeg_path = ffmpeg_path
                            AudioSegment.converter = ffmpeg_path
                            break
                    except Exception:
                        continue
        except Exception:
            pass

    def can_convert(self):
        """Check if conversion is possible"""
        return self.has_pydub and self.has_ffmpeg

    def set_ffmpeg_path(self, path, log_callback=None):
        """
        Set a custom ffmpeg path for Pydroid 3 or other environments

        Args:
            path: Path to ffmpeg executable
            log_callback: Function to call for logging

        Returns:
            True if ffmpeg is valid at that path, False otherwise
        """
        import subprocess
        try:
            result = subprocess.run([path, '-version'],
                                   capture_output=True,
                                   timeout=2)
            if result.returncode == 0:
                self.has_ffmpeg = True
                self.ffmpeg_path = path
                from pydub import AudioSegment
                AudioSegment.converter = path
                if log_callback:
                    log_safe(log_callback, f"✅ FFmpeg configured at: {path}")
                return True
        except Exception as e:
            if log_callback:
                log_safe(log_callback, f"❌ Invalid ffmpeg path: {e}")
        return False

    def convert_to_mp3(self, input_file, output_file=None, log_callback=None):
        """
        Convert audio file to MP3 format

        Args:
            input_file: Path to input audio file (.m4a, .opus, etc.)
            output_file: Path for output MP3 file (optional, auto-generated if None)
            log_callback: Function to call for logging

        Returns:
            Path to converted MP3 file, or None if conversion failed
        """
        if not self.can_convert():
            if log_callback:
                log_safe(log_callback, "⚠️ Conversion not available - pydub/ffmpeg not installed")
            return None

        try:
            from pydub import AudioSegment

            # Generate output filename if not provided
            if output_file is None:
                base_name = os.path.splitext(input_file)[0]
                output_file = f"{base_name}_converted.mp3"

            # Check if input file exists
            if not os.path.exists(input_file):
                if log_callback:
                    log_safe(log_callback, f"❌ Input file not found: {input_file}")
                return None

            # Detect input format
            input_ext = os.path.splitext(input_file)[1].lower()
            format_map = {
                '.m4a': 'm4a',
                '.opus': 'opus',
                '.ogg': 'ogg',
                '.webm': 'webm',
                '.mp4': 'mp4'
            }

            input_format = format_map.get(input_ext)
            if not input_format:
                if log_callback:
                    log_safe(log_callback, f"⚠️ Unsupported format: {input_ext}")
                return None

            if log_callback:
                log_safe(log_callback, f"🔄 Converting {os.path.basename(input_file)} to MP3...")

            # Load and convert audio
            audio = AudioSegment.from_file(input_file, format=input_format)
            audio.export(output_file, format='mp3', bitrate='192k')

            if log_callback:
                log_safe(log_callback, f"✅ Converted to: {os.path.basename(output_file)}")

            return output_file

        except Exception as e:
            if log_callback:
                log_safe(log_callback, f"❌ Conversion error: {e}")
            return None

    def test_playback(self, file_path):
        """
        Test if a file can be played by SoundLoader

        Args:
            file_path: Path to audio file

        Returns:
            True if file can be loaded, False otherwise
        """
        try:
            sound = SoundLoader.load(file_path)
            if sound:
                sound.unload()
                return True
            return False
        except Exception:
            return False

    def test_pygame_playback(self, file_path):
        """
        Test if a file can be played using pygame mixer

        Args:
            file_path: Path to audio file

        Returns:
            True if file can be loaded by pygame, False otherwise
        """
        try:
            is_mobile = self.env_detector.is_mobile if self.env_detector else False
            is_android = self.env_detector.is_android if self.env_detector else False
            player = PygameAudioPlayer(is_mobile=is_mobile, is_android=is_android)
            if player.load(file_path):
                player.unload()
                return True
            return False
        except Exception:
            return False

    def auto_convert_if_needed(self, file_path, log_callback=None):
        """
        Automatically convert file to MP3 if it can't be played
        Tries multiple fallback methods:
        1. Test with SoundLoader (Kivy default)
        2. Test with Pygame mixer (better codec support on Android/Pydroid 3)
        3. Convert with ffmpeg if available

        Args:
            file_path: Path to audio file
            log_callback: Function to call for logging

        Returns:
            Path to playable file (original or converted), or None if failed
        """
        # First, try to play the file with Kivy's SoundLoader
        if self.test_playback(file_path):
            return file_path

        # Second, try pygame mixer (better codec support on Android/Pydroid 3)
        if self.test_pygame_playback(file_path):
            if log_callback:
                log_safe(log_callback, f"✅ {os.path.basename(file_path)} playable with pygame fallback")
            return file_path

        # If both failed and file is in a convertible format, try ffmpeg conversion
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.m4a', '.opus', '.ogg', '.webm']:
            if log_callback:
                log_safe(log_callback, f"⚠️ {os.path.basename(file_path)} cannot be played directly")

            if self.can_convert():
                converted_file = self.convert_to_mp3(file_path, log_callback=log_callback)
                if converted_file and os.path.exists(converted_file):
                    return converted_file
            else:
                if log_callback:
                    log_safe(log_callback, "ℹ️ Audio conversion not available - ffmpeg not found")
                    log_safe(log_callback, "ℹ️ Note: Pygame fallback will be used for playback")

        return None


# ------------------- Configuration -------------------
CONFIG_FILE = "app_settings.json"

def load_settings():
    """Load app settings from config file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"mobile_mode": False}

def save_settings(settings):
    """Save app settings to config file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f)
    except Exception:
        pass

# ------------------- Utility -------------------
def sanitize_filename(name):
    return "".join(c if c.isalnum() or c in " ._-()" else "_" for c in name)

def log_safe(log_func, msg):
    # Schedule log update on the main thread (Kivy)
    try:
        Clock.schedule_once(lambda dt: log_func(msg))
    except Exception:
        # If scheduling fails for any reason, attempt direct call (best-effort)
        try:
            log_func(msg)
        except Exception:
            pass

def format_time(seconds):
    """Convert seconds to MM:SS format"""
    if seconds is None or seconds < 0:
        return "00:00"
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

def detect_speed():
    """Simulate internet speed detection (stub)."""
    try:
        r = requests.get("https://www.google.com", timeout=3)
        if r.elapsed.total_seconds() < 0.5:
            return "high"
        elif r.elapsed.total_seconds() < 1.5:
            return "medium"
        else:
            return "low"
    except Exception:
        return "medium"


# ------------------- Cover Art Helper -------------------
def extract_cover_art(file_path, cache_dir="cover_cache"):
    """Extract cover art from audio file and cache it"""
    os.makedirs(cache_dir, exist_ok=True)

    # Generate cache filename using basename for simplicity
    cache_file = os.path.join(cache_dir, f"{os.path.basename(file_path)}.jpg")

    # Return cached file if it exists
    if os.path.exists(cache_file):
        return cache_file

    try:
        audio = ID3(file_path)
        for tag in audio.values():
            if isinstance(tag, APIC):
                # Found cover art
                with open(cache_file, 'wb') as f:
                    f.write(tag.data)
                return cache_file
    except Exception:
        # No APIC or ID3 data — ignore
        pass

    return None

def download_cover_art(url, cache_dir="cover_cache", filename="cover.jpg"):
    """Download cover art from URL and cache it"""
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, filename)

    # Return cached file if it exists
    if os.path.exists(cache_file):
        return cache_file

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(cache_file, 'wb') as f:
                f.write(response.content)
            return cache_file
    except Exception:
        pass

    return None


# ------------------- Metadata -------------------
def embed_metadata(file_path, metadata, log_callback):
    """
    Safely embed metadata for both MP3 (ID3) and M4A (MP4) files.
    `log_callback` should be a function that accepts one string argument.
    """
    try:
        file_ext = os.path.splitext(file_path)[1].lower()

        # Handle M4A files
        if file_ext == '.m4a':
            try:
                audio = MP4(file_path)
                audio['\xa9nam'] = metadata.get("title", "Unknown Title")
                audio['\xa9ART'] = metadata.get("uploader", "Unknown Artist")
                audio['\xa9alb'] = metadata.get("album", "Streamed Playlist")

                # Add cover art for M4A
                if "thumbnail" in metadata and metadata.get("thumbnail"):
                    try:
                        resp = requests.get(metadata["thumbnail"], timeout=10)
                        if resp.status_code == 200:
                            from mutagen.mp4 import MP4Cover
                            audio['covr'] = [MP4Cover(resp.content, imageformat=MP4Cover.FORMAT_JPEG)]
                    except Exception:
                        pass

                audio.save(file_path)
                log_safe(log_callback, "✅ Metadata embedded (M4A).")
            except Exception as e:
                log_safe(log_callback, f"⚠️ Error saving M4A tags: {e}")
            return

        # Handle MP3 files
        audio = None
        # Try to load existing EasyID3 tags; if none exist, attempt to create them safely
        try:
            audio = EasyID3(file_path)
        except Exception:
            try:
                # Attempt to add ID3 tags using MP3 wrapper then reopen with EasyID3
                from mutagen.mp3 import MP3
                mp3 = MP3(file_path)
                try:
                    mp3.add_tags()
                except Exception:
                    pass
                audio = EasyID3(file_path)
            except Exception:
                log_safe(log_callback, "⚠️ Could not create ID3 tags; continuing without EasyID3 metadata.")
                audio = None

        if audio is not None:
            try:
                audio["title"] = metadata.get("title", "Unknown Title")
                audio["artist"] = metadata.get("uploader", "Unknown Artist")
                audio["album"] = metadata.get("album", "Streamed Playlist")
                audio.save(file_path)
                log_safe(log_callback, "✅ Metadata embedded (MP3).")
            except Exception as e:
                log_safe(log_callback, f"⚠️ Error saving EasyID3 tags: {e}")

        # Handle thumbnail separately using ID3 APIC frames for MP3
        if "thumbnail" in metadata and metadata.get("thumbnail"):
            try:
                resp = requests.get(metadata["thumbnail"], timeout=10)
                if resp.status_code == 200:
                    img_data = resp.content
                else:
                    img_data = None
            except Exception:
                img_data = None

            try:
                id3 = None
                try:
                    id3 = ID3(file_path)
                except Exception:
                    # Create ID3 header if missing
                    try:
                        id3 = ID3()
                    except Exception:
                        id3 = None

                if id3 is not None and img_data:
                    try:
                        id3.delall("APIC")
                    except Exception:
                        pass
                    id3.add(APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=img_data
                    ))
                    id3.save(file_path)
                    log_safe(log_callback, "🖼️ Embedded thumbnail.")
            except Exception as e:
                log_safe(log_callback, f"⚠️ Could not embed thumbnail: {e}")

    except Exception as e:
        log_safe(log_callback, f"⚠️ Error embedding metadata: {e}")


def get_metadata(file_path):
    """Extract metadata from audio file"""
    try:
        audio = EasyID3(file_path)
        return {
            'title': audio.get('title', ['Unknown Title'])[0],
            'artist': audio.get('artist', ['Unknown Artist'])[0],
            'album': audio.get('album', ['Unknown Album'])[0],
        }
    except Exception:
        return {
            'title': os.path.basename(file_path),
            'artist': 'Unknown Artist',
            'album': 'Unknown Album',
        }


# ------------------- yt_dlp Helpers -------------------
def get_playlist_entries(url):
    """Extract playlist entries for streaming."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info and info['entries'] is not None:
                return list(info['entries'])
            else:
                return [info]
    except Exception as e:
        print(f"Error getting playlist entries: {e}")
        return []


# ------------------- Queue Dialog -------------------
class QueueDialog(ModalView):
    def __init__(self, queue_data, current_index, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.95, 0.85)
        self.title = "Stream Queue"

        # Dark background
        with self.canvas.before:
            Color(0.09, 0.09, 0.09, 1)
            self.bg_rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(15)])
        self.bind(size=self._update_bg, pos=self._update_bg)

        layout = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(16))

        # Title with Spotify styling - larger for mobile
        title_label = MDLabel(
            text="Upcoming Songs",
            font_style="H5",
            halign="center",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            size_hint_y=None,
            height=dp(56)
        )
        layout.add_widget(title_label)

        # Queue list - responsive height
        scroll = ScrollView(size_hint=(1, 0.6))
        queue_layout = GridLayout(cols=1, spacing=dp(12), size_hint_y=None)
        queue_layout.bind(minimum_height=queue_layout.setter('height'))

        for i, entry in enumerate(queue_data):
            if i == current_index:
                prefix = "▶ NOW PLAYING"
                color = [0.11, 0.73, 0.33, 1]  # Spotify green
            else:
                prefix = f"{i+1}."
                color = [1, 1, 1, 1]  # White

            track_text = f"{prefix} {entry.get('title', 'Unknown')} - {entry.get('uploader', 'Unknown Artist')}"
            track_label = MDLabel(
                text=track_text,
                size_hint_y=None,
                height=dp(60),
                theme_text_color="Custom",
                text_color=color,
                halign='left',
                font_style="Body1"
            )
            queue_layout.add_widget(track_label)

        queue_layout.height = len(queue_data) * dp(72)
        scroll.add_widget(queue_layout)
        layout.add_widget(scroll)

        # Close button - larger for mobile
        close_btn = MDRaisedButton(
            text="Close",
            md_bg_color=[0.11, 0.73, 0.33, 1],
            size_hint_y=None,
            height=dp(56),
            font_size=dp(18),
            on_press=self.dismiss
        )
        layout.add_widget(close_btn)

        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


# ------------------- Download Manager -------------------
class DownloadManager:
    """Handles download operations with proper thread safety"""
    def __init__(self, ui):
        self.ui = ui
        self.download_stop_flag = False
        self.download_thread = None
        self.mobile_mode = False

    def set_mobile_mode(self, enabled):
        """Set mobile mode on/off"""
        self.mobile_mode = enabled

    def start_download(self, url):
        """Start a download in a background thread"""
        self.download_stop_flag = False
        Clock.schedule_once(lambda dt: self.ui.show_download_progress())
        self.download_thread = threading.Thread(target=self._download_thread, args=(url,), daemon=True)
        self.download_thread.start()

    def _download_thread(self, url):
        """Download thread function"""
        try:
            if self.mobile_mode:
                self._download_audio_mobile(url)
            else:
                self._download_audio_desktop(url)
            Clock.schedule_once(lambda dt: self.ui.refresh_file_list())
            Clock.schedule_once(lambda dt: self.ui.log("✅ Download completed."))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.ui.log(f"❌ Download error: {e}"))
        finally:
            Clock.schedule_once(lambda dt: self.ui.hide_download_progress())

    def cancel_download(self):
        """Cancel the current download"""
        self.download_stop_flag = True
        log_safe(self.ui.log, "⏹ Download cancelled")
        Clock.schedule_once(lambda dt: self.ui.hide_download_progress())

    def _download_audio_mobile(self, url):
        """Mobile mode: Download audio without FFmpeg conversion (m4a format)"""
        log_safe(self.ui.log, f"📱 Mobile mode: Fetching info from: {url}")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get('entries', [info])
        total_items = len(entries)
        log_safe(self.ui.log, f"🔎 Found {total_items} item(s). Starting download...")

        Clock.schedule_once(lambda dt: self.ui.update_download_title(f"Downloading {total_items} items..."))

        for i, entry in enumerate(entries):
            if self.download_stop_flag:
                log_safe(self.ui.log, "Download cancelled")
                break

            progress = (i / total_items) * 100 if total_items > 0 else 0
            status = f"Downloading {i+1}/{total_items}: {entry.get('title', '')[:30]}..."
            Clock.schedule_once(lambda dt, p=progress, s=status: self.ui.update_download_progress(p, s))
            Clock.schedule_once(lambda dt, e=entry, idx=i: self.ui.log(f"🎶 Downloading {idx+1}/{total_items}: {e.get('title','')}"))

            # Mobile mode: ONLY MP3 and OGG containers (pygame on Android cannot play WebM/M4A/Opus)
            # Note: NO WebM/Opus/M4A fallback - only MP3 and OGG containers work on Pydroid 3
            format_attempts = [
                'bestaudio[ext=mp3]/bestaudio[acodec=mp3]',
                'bestaudio[ext=ogg]/bestaudio[acodec=vorbis]',
                'worst[ext=mp3]/worst[acodec=mp3]',
                'worst[ext=ogg]/worst[acodec=vorbis]'
            ]

            audio_file = None
            try:
                os.makedirs('temp', exist_ok=True)

                for format_str in format_attempts:
                    if self.download_stop_flag:
                        break

                    Clock.schedule_once(lambda dt, f=format_str: self.ui.log(f"🔄 Trying format: {f.split('/')[0]}..."))
                    audio_file = self._try_download_with_format(entry, format_str)

                    if audio_file and os.path.exists(audio_file):
                        ext = os.path.splitext(audio_file)[1].lower()
                        Clock.schedule_once(lambda dt, e=ext: self.ui.log(f"✅ Downloaded as {e} format"))
                        break
                    else:
                        if os.path.exists('temp'):
                            for f in os.listdir('temp'):
                                try:
                                    os.remove(os.path.join('temp', f))
                                except:
                                    pass

                if audio_file and os.path.exists(audio_file):
                    title = entry.get('title', 'Unknown Title')
                    artist = entry.get('uploader', 'Unknown Artist')
                    ext = os.path.splitext(audio_file)[1]
                    final_name = sanitize_filename(f"{artist} - {title}{ext}")

                    # Safe file move with retry
                    try:
                        if os.path.exists(final_name):
                            os.remove(final_name)
                        shutil.move(audio_file, final_name)
                    except Exception as move_err:
                        log_safe(self.ui.log, f"⚠️ Move error, trying copy: {move_err}")
                        shutil.copy2(audio_file, final_name)
                        try:
                            os.remove(audio_file)
                        except Exception:
                            pass

                    # Embed metadata on main thread
                    Clock.schedule_once(lambda dt, fn=final_name, e=entry: self._embed_metadata_safe(fn, e))
                    Clock.schedule_once(lambda dt, fn=final_name: self.ui.log(f"✅ Saved: {fn}"))
                else:
                    Clock.schedule_once(lambda dt, t=entry.get('title',''): self.ui.log(f"❌ Failed to download {t}: No compatible format found"))
                    Clock.schedule_once(lambda dt: self.ui.log(f"ℹ️ This video may only have Opus/M4A which cannot be played without ffmpeg"))
            except Exception as e:
                Clock.schedule_once(lambda dt, t=entry.get('title',''), err=e: self.ui.log(f"❌ Error downloading {t}: {err}"))

        if not self.download_stop_flag:
            Clock.schedule_once(lambda dt: self.ui.update_download_progress(100, "Download completed!"))

        # cleanup temp folder if exists
        try:
            if os.path.exists('temp'):
                shutil.rmtree('temp')
        except Exception:
            pass

    def _download_audio_desktop(self, url):
        """Desktop mode: Download with FFmpeg MP3 conversion (high quality)"""
        log_safe(self.ui.log, f"💻 Desktop mode: Fetching info from: {url}")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get('entries', [info])
        total_items = len(entries)
        log_safe(self.ui.log, f"🔎 Found {total_items} item(s). Starting download...")

        Clock.schedule_once(lambda dt: self.ui.update_download_title(f"Downloading {total_items} items..."))

        for i, entry in enumerate(entries):
            if self.download_stop_flag:
                log_safe(self.ui.log, "Download cancelled")
                break

            progress = (i / total_items) * 100 if total_items > 0 else 0
            status = f"Downloading {i+1}/{total_items}: {entry.get('title', '')[:30]}..."
            Clock.schedule_once(lambda dt, p=progress, s=status: self.ui.update_download_progress(p, s))
            Clock.schedule_once(lambda dt, e=entry, idx=i: self.ui.log(f"🎶 Downloading {idx+1}/{total_items}: {e.get('title','')}"))

            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'outtmpl': os.path.join('temp', 'temp_audio.%(ext)s'),
            }

            try:
                os.makedirs('temp', exist_ok=True)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([entry.get('webpage_url') or entry.get('url')])

                # find produced file
                temp_files = os.listdir('temp')
                mp3_file = None
                for tf in temp_files:
                    if tf.startswith('temp_audio') and (tf.endswith('.mp3') or tf.endswith('.m4a') or tf.endswith('.webm')):
                        mp3_file = os.path.join('temp', tf)
                        break

                if mp3_file and os.path.exists(mp3_file):
                    title = entry.get('title', 'Unknown Title')
                    artist = entry.get('uploader', 'Unknown Artist')
                    final_name = sanitize_filename(f"{artist} - {title}.mp3")

                    # Safe file move
                    try:
                        if os.path.exists(final_name):
                            os.remove(final_name)
                        os.replace(mp3_file, final_name)
                    except Exception:
                        shutil.move(mp3_file, final_name)

                    # Embed metadata on main thread
                    Clock.schedule_once(lambda dt, fn=final_name, e=entry: self._embed_metadata_safe(fn, e))
                    Clock.schedule_once(lambda dt, fn=final_name: self.ui.log(f"✅ Saved: {fn}"))
                else:
                    Clock.schedule_once(lambda dt, t=entry.get('title',''): self.ui.log(f"⚠️ Could not find output for: {t}"))
            except Exception as e:
                Clock.schedule_once(lambda dt, t=entry.get('title',''), err=e: self.ui.log(f"❌ Error downloading {t}: {err}"))

        if not self.download_stop_flag:
            Clock.schedule_once(lambda dt: self.ui.update_download_progress(100, "Download completed!"))

        # cleanup temp folder if exists
        try:
            if os.path.exists('temp'):
                shutil.rmtree('temp')
        except Exception:
            pass

    def _embed_metadata_safe(self, file_path, metadata):
        """Embed metadata safely from main thread"""
        try:
            embed_metadata(file_path, metadata, self.ui.log)
        except Exception as e:
            log_safe(self.ui.log, f"⚠️ Error embedding metadata: {e}")

    def _try_download_with_format(self, entry, format_string, output_dir='temp'):
        """
        Try downloading with a specific format string.
        Returns the path to the downloaded file, or None if failed.
        """
        try:
            os.makedirs(output_dir, exist_ok=True)

            ydl_opts = {
                'format': format_string,
                'quiet': True,
                'no_warnings': True,
                'outtmpl': os.path.join(output_dir, 'temp_audio.%(ext)s'),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([entry.get('webpage_url') or entry.get('url')])

            temp_files = os.listdir(output_dir)
            for tf in temp_files:
                if tf.startswith('temp_audio'):
                    return os.path.join(output_dir, tf)

            return None
        except Exception as e:
            log_safe(self.ui.log, f"⚠️ Format '{format_string[:30]}...' failed: {str(e)[:50]}")
            return None


# ------------------- Stream Player -------------------
class StreamPlayer:
    def __init__(self, ui, is_android=False):
        self.ui = ui
        self.sound = None
        self.stop_flag = False
        self.pause_flag = False
        self.skip_flag = False
        self.current_entry = None
        self.queue = []
        self.current_index = 0
        self.temp_dir = "stream_cache"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.next_download_thread = None
        self.current_file = None
        self.progress_update_event = None
        self.playback_start_time = 0
        self.total_paused_time = 0
        self.last_pause_time = 0
        self.played_files = set()  # Track played files for cleanup
        self.stream_stop_flag = False  # Separate flag for stream cancellation
        self.pause_position = 0  # Track position when paused
        self.mobile_mode = False  # Mobile mode flag
        self.audio_converter = AudioConverter()  # Audio converter for m4a files
        self.using_pygame = False  # Track if using pygame fallback player
        self.is_android = is_android
        self.wake_lock_manager = WakeLockManager(is_android=is_android)

    def cleanup_temp_directory(self):
        """Safely remove files in temp_dir but do not remove file currently playing."""
        try:
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                return

            files_deleted = 0
            for fname in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, fname)
                # Skip currently playing file (if any)
                try:
                    if self.current_file and os.path.abspath(file_path) == os.path.abspath(self.current_file):
                        continue
                except Exception:
                    pass

                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        files_deleted += 1
                    except Exception as e:
                        log_safe(self.ui.log, f"⚠️ Could not delete {fname}: {e}")

            if files_deleted > 0:
                log_safe(self.ui.log, f"🧹 Deleted {files_deleted} temporary file(s)")
        except Exception as e:
            log_safe(self.ui.log, f"⚠️ Error cleaning temp directory: {e}")

    def cleanup_played_files(self):
        """Clean up played files to save space"""
        try:
            files_deleted = 0
            for filename in list(self.played_files):
                file_path = os.path.join(self.temp_dir, filename)
                if os.path.exists(file_path):
                    try:
                        # Extract cover art BEFORE deleting the audio file
                        cover_path = extract_cover_art(file_path)
                        os.remove(file_path)
                        files_deleted += 1
                        # Also clean up cover art if present
                        if cover_path and os.path.exists(cover_path):
                            try:
                                os.remove(cover_path)
                            except Exception as e:
                                log_safe(self.ui.log, f"⚠️ Could not delete cover art {cover_path}: {e}")
                    except Exception as e:
                        log_safe(self.ui.log, f"⚠️ Could not delete {filename}: {e}")
                try:
                    self.played_files.remove(filename)
                except KeyError:
                    pass

            if files_deleted > 0:
                log_safe(self.ui.log, f"🧹 Deleted {files_deleted} played song(s)")

        except Exception as e:
            log_safe(self.ui.log, f"⚠️ Error during cleanup: {e}")

    def safe_delete_file(self, file_path):
        """Safely delete a file with error handling"""
        try:
            if file_path and os.path.exists(file_path):
                # Extract cover art before removing audio file
                cover_path = extract_cover_art(file_path)
                try:
                    os.remove(file_path)
                except Exception as e:
                    log_safe(self.ui.log, f"⚠️ Could not delete {os.path.basename(file_path)}: {e}")
                    return False

                # delete cached cover art if any
                if cover_path and os.path.exists(cover_path):
                    try:
                        os.remove(cover_path)
                    except Exception as e:
                        log_safe(self.ui.log, f"⚠️ Could not delete cover art {cover_path}: {e}")
                return True
        except Exception as e:
            log_safe(self.ui.log, f"⚠️ Could not delete {os.path.basename(file_path)}: {e}")
        return False

    def stream_playlist(self, url):
        """Queue and play songs sequentially, pre-downloading next."""
        self.stop_flag = False
        self.stream_stop_flag = False
        self.pause_flag = False
        self.skip_flag = False
        self.current_index = 0
        self.played_files.clear()

        # Clean up temp directory before starting new stream
        self.cleanup_temp_directory()

        try:
            entries = get_playlist_entries(url)
            if not entries:
                log_safe(self.ui.log, "❌ No entries found or invalid URL")
                return

            speed = detect_speed()
            log_safe(self.ui.log, f"🌐 Detected speed: {speed}")
            log_safe(self.ui.log, f"📜 Found {len(entries)} track(s).")

            self.queue = entries

            for i in range(len(entries)):
                if self.stop_flag or self.stream_stop_flag:
                    break

                self.current_index = i
                entry = entries[i]

                # Wait for previous download to finish if it exists
                if self.next_download_thread and self.next_download_thread.is_alive():
                    self.next_download_thread.join(timeout=30)

                # Show download progress in the UI
                Clock.schedule_once(lambda dt: self.ui.show_stream_progress())
                Clock.schedule_once(lambda dt: self.ui.update_stream_progress(0, f"Downloading: {entry.get('title', 'Unknown')[:30]}..."))

                filename = self.download_song(entry, speed)

                # Hide stream progress when done
                Clock.schedule_once(lambda dt: self.ui.hide_stream_progress())

                if not filename:
                    log_safe(self.ui.log, f"⚠️ Failed to download {entry.get('title')}, skipping...")
                    continue

                # Start background download of next song
                if i + 1 < len(entries):
                    next_entry = entries[i + 1]
                    self.next_download_thread = threading.Thread(
                        target=self.download_song,
                        args=(next_entry, speed),
                        daemon=True
                    )
                    self.next_download_thread.start()

                # Update queue display
                Clock.schedule_once(lambda dt, q=self.queue, idx=self.current_index: self.ui.update_queue_display(q, idx))

                # Play the song
                playback_success = self.play_song(filename, entry)

                # Immediately clean up the played file after playback
                if filename and os.path.exists(filename):
                    self.safe_delete_file(filename)
                    log_safe(self.ui.log, f"🧹 Deleted: {os.path.basename(filename)}")

                # Clean up any other played files
                self.cleanup_played_files()

                if not playback_success and not self.stop_flag and not self.skip_flag and not self.stream_stop_flag:
                    log_safe(self.ui.log, f"⏭️ Skipping unplayable song: {entry.get('title')}")
                    continue

            if not self.stop_flag and not self.stream_stop_flag:
                log_safe(self.ui.log, "✅ Playlist finished.")

        except Exception as e:
            log_safe(self.ui.log, f"❌ Error in stream_playlist: {e}")
        finally:
            # Clear queue display when done
            Clock.schedule_once(lambda dt: self.ui.clear_queue_display())
            # Final cleanup - delete all remaining files (except possibly a playing file)
            self.cleanup_temp_directory()

    def set_mobile_mode(self, enabled):
        """Set mobile mode on/off"""
        self.mobile_mode = enabled

    def download_song(self, entry, speed):
        """Download full song to temp folder based on speed quality and mode."""
        try:
            url = entry.get("webpage_url", entry.get("url"))
            if not url:
                return None

            safe_title = sanitize_filename(entry.get("title", "unknown"))
            out_path_template = os.path.join(self.temp_dir, f"{safe_title}.%(ext)s")
            os.makedirs(self.temp_dir, exist_ok=True)

            # Check for existing files
            for ext in ['.mp3', '.m4a', '.webm']:
                expected_file = os.path.join(self.temp_dir, f"{safe_title}{ext}")
                if os.path.exists(expected_file):
                    return expected_file

            # Progress hook for yt-dlp
            def progress_hook(d):
                try:
                    status = d.get('status')
                    if status == 'downloading' and not self.stream_stop_flag:
                        # percent may be in _percent_str or percent fields
                        percent = 0.0
                        if '_percent_str' in d:
                            pct = d.get('_percent_str', '0%').strip().strip('%')
                            try:
                                percent = float(pct)
                            except Exception:
                                percent = 0.0
                        elif 'percent' in d:
                            try:
                                percent = float(d.get('percent', 0.0))
                            except Exception:
                                percent = 0.0

                        speed_str = d.get('_speed_str', 'N/A')
                        total_size = d.get('_total_bytes_str', 'N/A')
                        if not self.stream_stop_flag:
                            status_text = f"Downloading: {speed_str} - {total_size}"
                            Clock.schedule_once(lambda dt, p=percent, s=status_text: self.ui.update_stream_progress(p, s))

                    elif d.get('status') == 'finished' and not self.stream_stop_flag:
                        Clock.schedule_once(lambda dt: self.ui.update_stream_progress(100, "Processing..."))
                except Exception:
                    pass

            # Configure download using centralized environment options
            if hasattr(self.ui, 'env_detector'):
                ydl_opts = self.ui.env_detector.get_download_options().copy()
            else:
                ydl_opts = {
                    "format": "bestaudio/best",
                }

            # Add call-specific options (outtmpl, progress hooks)
            ydl_opts["quiet"] = True
            ydl_opts["no_warnings"] = True
            ydl_opts["outtmpl"] = out_path_template
            ydl_opts["progress_hooks"] = [progress_hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Check if we were cancelled during download
            if self.stream_stop_flag:
                # Clean up any downloaded files
                for ext in ['.mp3', '.m4a', '.webm']:
                    temp_file = os.path.join(self.temp_dir, f"{safe_title}{ext}")
                    if os.path.exists(temp_file):
                        self.safe_delete_file(temp_file)
                return None

            # Find the actual downloaded file in temp_dir
            actual_path = None
            for file in os.listdir(self.temp_dir):
                if file.startswith(safe_title):
                    actual_path = os.path.join(self.temp_dir, file)
                    break

            if actual_path and os.path.exists(actual_path):
                # Test if file is playable, auto-convert if needed
                playable_path = self.audio_converter.auto_convert_if_needed(actual_path, self.ui.log)

                if not playable_path:
                    log_safe(self.ui.log, f"❌ Downloaded file is unplayable and cannot be converted: {safe_title}")
                    self.safe_delete_file(actual_path)
                    return None

                # If conversion happened, clean up the original file
                if playable_path != actual_path:
                    self.safe_delete_file(actual_path)
                    actual_path = playable_path

                # Embed metadata (safe call on main thread)
                try:
                    embed_metadata(actual_path, entry, self.ui.log)
                except Exception:
                    pass

                log_safe(self.ui.log, f"🎵 Downloaded: {safe_title}")
                return actual_path
            else:
                log_safe(self.ui.log, f"❌ File not found after download: {safe_title}")
                return None

        except Exception as e:
            log_safe(self.ui.log, f"❌ Error downloading {entry.get('title')}: {e}")
            return None

    def play_song(self, filepath, entry):
        """Play a downloaded file with robust error handling and pygame fallback."""
        if self.stop_flag or self.stream_stop_flag or not filepath or not os.path.exists(filepath):
            return False

        if self.sound:
            try:
                if hasattr(self.sound, 'stop'):
                    self.sound.stop()
                if hasattr(self.sound, 'unload'):
                    self.sound.unload()
            except Exception:
                pass

        self.current_file = filepath
        self.current_entry = entry
        self.using_pygame = False

        # Try to load the sound file with Kivy's SoundLoader first
        try:
            self.sound = SoundLoader.load(filepath)
            if not self.sound:
                # Kivy failed, try pygame as fallback
                log_safe(self.ui.log, f"ℹ️ Kivy SoundLoader failed, trying pygame fallback...")
                is_mobile = self.env_detector.is_mobile if hasattr(self, 'env_detector') and self.env_detector else False
                pygame_player = PygameAudioPlayer(is_mobile=is_mobile, is_android=self.is_android)
                if pygame_player.load(filepath):
                    self.sound = pygame_player
                    self.using_pygame = True
                    log_safe(self.ui.log, f"✅ Using pygame fallback for: {entry.get('title')}")
                else:
                    log_safe(self.ui.log, f"❌ Could not load audio file with any player: {entry.get('title')}")
                    self.safe_delete_file(filepath)
                    return False

            # Test if the sound is playable
            if not hasattr(self.sound, 'length') or self.sound.length <= 0:
                log_safe(self.ui.log, f"❌ Invalid audio file: {entry.get('title')}")
                try:
                    if hasattr(self.sound, 'unload'):
                        self.sound.unload()
                except Exception:
                    pass
                self.sound = None
                self.safe_delete_file(filepath)
                return False

        except Exception as e:
            # Kivy failed, try pygame as fallback
            log_safe(self.ui.log, f"ℹ️ Kivy error: {e}, trying pygame fallback...")
            try:
                is_mobile = self.env_detector.is_mobile if hasattr(self, 'env_detector') and self.env_detector else False
                pygame_player = PygameAudioPlayer(is_mobile=is_mobile, is_android=self.is_android)
                if pygame_player.load(filepath):
                    self.sound = pygame_player
                    self.using_pygame = True
                    log_safe(self.ui.log, f"✅ Using pygame fallback for: {entry.get('title')}")
                else:
                    log_safe(self.ui.log, f"❌ Could not load audio file with any player: {entry.get('title')}")
                    self.safe_delete_file(filepath)
                    return False
            except Exception as e2:
                log_safe(self.ui.log, f"❌ Both Kivy and pygame failed: {e2}")
                self.safe_delete_file(filepath)
                return False

        # Reset timing variables
        self.playback_start_time = time.time()
        self.total_paused_time = 0
        self.last_pause_time = 0
        self.skip_flag = False

        # Update UI with current track info and cover art
        Clock.schedule_once(lambda dt, e=entry, fp=filepath: self.ui.update_current_track(e, fp))

        try:
            self.sound.play()
            # Acquire wake lock for background playback
            self.wake_lock_manager.acquire()
            log_safe(self.ui.log, f"▶️ Now playing: {entry.get('title', 'Unknown')}")
        except Exception as e:
            log_safe(self.ui.log, f"❌ Error playing {entry.get('title')}: {e}")
            self.safe_delete_file(filepath)
            return False

        # Start progress updates
        self.start_progress_updates()

        # Calculate duration (use entry duration or sound length)
        duration = entry.get('duration', 0) or 0
        if duration <= 0 and self.sound:
            duration = self.sound.length or 0

        # Wait until song ends or user stops/skips
        start_time = time.time()
        timeout = duration + 10 if duration > 0 else 300  # default timeout if unknown

        playback_success = True
        try:
            while (self.sound and
                   not self.stop_flag and not self.skip_flag and not self.stream_stop_flag and
                   (time.time() - start_time) < timeout):

                # Check if sound is still valid and playing (or paused)
                sound_state = getattr(self.sound, 'state', None)
                if sound_state != 'play' and not self.pause_flag:
                    # Song ended naturally (only exit if not paused)
                    break

                if self.pause_flag:
                    # Wait while paused (sound is stopped but we're waiting to resume)
                    while self.pause_flag and not self.stop_flag and not self.skip_flag and not self.stream_stop_flag:
                        time.sleep(0.1)
                    # After resuming, continue the loop to check if song is still playing
                else:
                    time.sleep(0.5)
        except Exception as e:
            log_safe(self.ui.log, f"❌ Playback error for {entry.get('title')}: {e}")
            playback_success = False

        self.stop_progress_updates()

        # Release wake lock when playback ends (naturally or stopped/skipped)
        # This ensures wake lock is released for both Kivy SoundLoader and pygame fallback
        self.wake_lock_manager.release()

        if self.sound:
            try:
                self.sound.stop()
                self.sound.unload()
            except Exception:
                pass
            self.sound = None

        # Mark file for immediate deletion (no longer keeping in played_files set)
        if filepath and os.path.exists(filepath):
            filename = os.path.basename(filepath)
            self.played_files.add(filename)

        # If we skipped, log it
        if self.skip_flag:
            log_safe(self.ui.log, "⏩ Song skipped")
            self.skip_flag = False

        return playback_success and not self.stop_flag and not self.stream_stop_flag

    def start_progress_updates(self):
        """Start updating playback progress"""
        self.stop_progress_updates()
        try:
            self.progress_update_event = Clock.schedule_interval(self.update_playback_progress, 0.5)
        except Exception:
            self.progress_update_event = None

    def stop_progress_updates(self):
        """Stop playback progress updates"""
        if self.progress_update_event:
            try:
                self.progress_update_event.cancel()
            except Exception:
                pass
            self.progress_update_event = None

    def update_playback_progress(self, dt):
        """Update playback progress bar and time using manual timing"""
        if self.sound and getattr(self.sound, 'state', None) == 'play' and not self.pause_flag:
            current_time = time.time() - self.playback_start_time - self.total_paused_time

            # Get duration from entry or sound
            duration = 0
            if self.current_entry and 'duration' in self.current_entry:
                try:
                    duration = float(self.current_entry['duration'] or 0)
                except Exception:
                    duration = 0
            elif self.sound and getattr(self.sound, 'length', 0) > 0:
                duration = self.sound.length

            # If we don't know duration, use a default (3 minutes)
            if duration <= 0:
                duration = 180

            progress = (current_time / duration) * 100 if duration > 0 else 0

            Clock.schedule_once(lambda dt, p=progress, ct=current_time, d=duration: self.ui.update_playback_progress(p, ct, d))

    def pause(self):
        """Pause current playback (works with both Kivy and pygame)"""
        if self.sound and getattr(self.sound, 'state', None) == 'play':
            # Save current position before stopping
            try:
                self.pause_position = self.sound.get_pos()
                # If get_pos() returns None or 0, calculate from elapsed time
                if not self.pause_position or self.pause_position <= 0:
                    self.pause_position = time.time() - self.playback_start_time - self.total_paused_time
            except Exception:
                # Calculate position from elapsed time if get_pos() fails
                self.pause_position = time.time() - self.playback_start_time - self.total_paused_time

            # Pause the sound (different methods for Kivy vs pygame)
            try:
                if self.using_pygame:
                    self.sound.pause()
                else:
                    self.sound.stop()
            except Exception:
                pass

            self.pause_flag = True
            # Record pause time for progress tracking
            if self.last_pause_time == 0:
                self.last_pause_time = time.time()
            # Release wake lock when paused to save battery
            self.wake_lock_manager.release()
            Clock.schedule_once(lambda dt: self.ui.update_playback_state("Paused"))

    def resume(self):
        """Resume paused playback (works with both Kivy and pygame)"""
        if self.sound and self.pause_flag:
            # Update total paused time
            if self.last_pause_time > 0:
                self.total_paused_time += time.time() - self.last_pause_time
                self.last_pause_time = 0

            # Resume playback with proper seek timing
            try:
                if self.using_pygame:
                    # Pygame has unpause method
                    self.sound.unpause()
                else:
                    # Kivy needs play + seek
                    self.sound.play()
                    # CRITICAL: Must delay seek() after play() - Kivy audio pipeline needs time to initialize
                    # Use Clock.schedule_once with 0.1s delay for reliable seeking
                    if self.pause_position and self.pause_position > 0:
                        def do_seek(dt):
                            try:
                                if self.sound and getattr(self.sound, 'state', None) == 'play':
                                    self.sound.seek(self.pause_position)
                            except Exception as e:
                                log_safe(self.ui.log, f"⚠️ Seek failed, using timing fallback: {e}")
                                # Fallback: adjust timing if seek not supported
                                self.playback_start_time = time.time() - self.pause_position - self.total_paused_time

                        Clock.schedule_once(do_seek, 0.1)
                        self.pause_position = 0
            except Exception as e:
                log_safe(self.ui.log, f"⚠️ Error resuming playback: {e}")

            self.pause_flag = False
            # Re-acquire wake lock when resuming
            self.wake_lock_manager.acquire()
            Clock.schedule_once(lambda dt: self.ui.update_playback_state("Playing"))

    def toggle_pause(self):
        """Toggle pause/resume"""
        if self.pause_flag:
            self.resume()
        else:
            self.pause()

    def skip(self):
        """Skip the current song"""
        if self.sound and getattr(self.sound, 'state', None) == 'play':
            self.skip_flag = True
            try:
                self.sound.stop()
            except Exception:
                pass

    def show_queue(self):
        """Show the current queue"""
        if self.queue:
            Clock.schedule_once(lambda dt: self._show_queue())
        else:
            log_safe(self.ui.log, "📜 No active queue")

    def _show_queue(self):
        """Show queue dialog"""
        dialog = QueueDialog(self.queue, self.current_index)
        dialog.open()

    def stop(self):
        self.stop_flag = True
        self.stream_stop_flag = True
        self.skip_flag = False
        self.pause_flag = False
        self.stop_progress_updates()
        # Release wake lock when stopping
        self.wake_lock_manager.release()
        if self.sound:
            try:
                self.sound.stop()
                self.sound.unload()
            except Exception:
                pass
            self.sound = None
        # Clean up all files when stopping
        self.cleanup_temp_directory()


# ------------------- Kivy UI -------------------
class DownloaderUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=0, padding=0, **kwargs)

        print("\n" + "="*60)
        print("INITIALIZING MUSIC PLAYER APP")
        print("="*60)

        self.env_detector = EnvironmentDetector()
        print(self.env_detector.print_debug_info())
        print("="*60 + "\n")

        self.current_sound = None
        self.streamer = StreamPlayer(self, is_android=self.env_detector.is_android)
        self.download_manager = DownloadManager(self)
        self.audio_converter = AudioConverter(env_detector=self.env_detector)

        self.settings = load_settings()

        if self.env_detector.is_mobile:
            self.mobile_mode = True
            print(f"AUTO-DETECTED MOBILE MODE: {self.env_detector.audio_mode}")
        else:
            self.mobile_mode = self.settings.get("mobile_mode", False)

        self.download_manager.set_mobile_mode(self.mobile_mode)
        self.streamer.set_mobile_mode(self.mobile_mode)
        self.streamer.env_detector = self.env_detector

        # Track playback time for local files
        self.local_play_start_time = 0
        self.local_total_paused_time = 0
        self.local_last_pause_time = 0
        self.local_is_paused = False

        # Set dark Spotify background
        with self.canvas.before:
            Color(0.07, 0.07, 0.07, 1)  # #121212
            self.rect = RoundedRectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        # Build the UI
        self.build_ui()

        # Set default cover art
        self.set_default_cover()

        self.refresh_file_list()

    def _update_rect(self, instance, value):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def show_debug_info(self, instance=None):
        """Show complete debug information dialog"""
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.label import Label

        debug_text = self.env_detector.print_debug_info()

        dialog = ModalView(size_hint=(0.9, 0.8))
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        layout.add_widget(Label(
            text="[b]Environment Debug Information[/b]",
            size_hint_y=0.08,
            font_size='18sp',
            markup=True
        ))

        scroll = ScrollView(size_hint=(1, 0.84))
        debug_label = Label(
            text=debug_text,
            size_hint_y=None,
            font_size='12sp',
            halign='left',
            valign='top',
            markup=False
        )
        debug_label.bind(texture_size=debug_label.setter('size'))
        scroll.add_widget(debug_label)
        layout.add_widget(scroll)

        close_btn = Button(text="Close", size_hint_y=0.08)
        close_btn.bind(on_press=lambda x: dialog.dismiss())
        layout.add_widget(close_btn)

        dialog.add_widget(layout)
        dialog.open()

    def toggle_mobile_mode(self, instance=None):
        """Toggle mobile/desktop mode"""
        self.mobile_mode = not self.mobile_mode
        self.settings["mobile_mode"] = self.mobile_mode
        save_settings(self.settings)

        # Update managers
        self.download_manager.set_mobile_mode(self.mobile_mode)
        self.streamer.set_mobile_mode(self.mobile_mode)

        # Update button
        self.mode_btn.text = "📱 Mobile Mode" if self.mobile_mode else "💻 Desktop Mode"
        self.mode_btn.md_bg_color = [0.2, 0.6, 1.0, 1] if self.mobile_mode else [0.11, 0.73, 0.33, 1]

        mode_text = "📱 Mobile mode" if self.mobile_mode else "💻 Desktop mode"
        self.log(f"Switched to {mode_text}")
        if self.mobile_mode:
            self.log("ℹ️ Mobile: No FFmpeg, downloads m4a format")
        else:
            self.log("ℹ️ Desktop: Uses FFmpeg for MP3 conversion")

    def build_ui(self):
        """Build the user interface - Spotify style"""
        # Clear any existing widgets
        self.clear_widgets()

        # Fixed top section (always visible) - Input and action buttons
        top_section = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(250), spacing=dp(12), padding=dp(20))

        # Mode switcher button
        self.mode_btn = MDRaisedButton(
            text="📱 Mobile Mode" if self.mobile_mode else "💻 Desktop Mode",
            md_bg_color=[0.2, 0.6, 1.0, 1] if self.mobile_mode else [0.11, 0.73, 0.33, 1],
            size_hint=(1, None),
            height=dp(48),
            font_size=dp(16),
            on_press=self.toggle_mobile_mode
        )
        top_section.add_widget(self.mode_btn)

        # Debug info button
        self.debug_btn = MDRaisedButton(
            text=f"🔍 Debug Info ({self.env_detector.get_status_summary()})",
            md_bg_color=[0.6, 0.4, 0.8, 1],
            size_hint=(1, None),
            height=dp(40),
            font_size=dp(14),
            on_press=self.show_debug_info
        )
        top_section.add_widget(self.debug_btn)

        # Input section with Spotify styling - larger for mobile
        self.url_input = MDTextField(
            hint_text="Enter YouTube/SoundCloud link...",
            mode="rectangle",
            size_hint=(1, None),
            height=dp(64),
            font_size=dp(18)
        )
        top_section.add_widget(self.url_input)

        # Stream button - full width for mobile
        self.stream_btn = MDRaisedButton(
            text="Stream",
            md_bg_color=[0.11, 0.73, 0.33, 1],
            size_hint=(1, None),
            height=dp(56),
            font_size=dp(18),
            on_press=self.start_stream
        )
        top_section.add_widget(self.stream_btn)

        self.add_widget(top_section)

        # Scrollable content area with responsive bottom padding
        main_content = BoxLayout(orientation='vertical', spacing=dp(16), padding=[dp(20), dp(12), dp(20), dp(100)], size_hint_y=None)
        main_content.bind(minimum_height=main_content.setter('height'))

        # Now Playing Card - larger for mobile
        now_playing_card = MDCard(
            size_hint_y=None,
            height=dp(480),
            md_bg_color=[0.09, 0.09, 0.09, 1],
            radius=[dp(15)],
            padding=dp(20)
        )

        card_content = BoxLayout(orientation='vertical', spacing=dp(12))

        # Cover art - larger for mobile
        self.cover_art = Image(
            size_hint=(1, None),
            height=dp(280),
            source='',
            allow_stretch=True,
            keep_ratio=True
        )
        card_content.add_widget(self.cover_art)

        # Track info - larger fonts for mobile
        self.track_title = MDLabel(
            text="No track playing",
            font_style="H5",
            halign="center",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            size_hint_y=None,
            height=dp(40)
        )
        self.track_artist = MDLabel(
            text="",
            font_style="Body1",
            halign="center",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            size_hint_y=None,
            height=dp(28)
        )
        self.track_album = MDLabel(
            text="",
            font_style="Body2",
            halign="center",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            size_hint_y=None,
            height=dp(28)
        )
        self.track_duration = MDLabel(
            text="",
            font_style="Caption",
            halign="center",
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
            size_hint_y=None,
            height=dp(24)
        )
        self.queue_info = MDLabel(
            text="Queue: 0 songs",
            font_style="Body2",
            halign="center",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            size_hint_y=None,
            height=dp(28)
        )

        card_content.add_widget(self.track_title)
        card_content.add_widget(self.track_artist)
        card_content.add_widget(self.track_album)
        card_content.add_widget(self.track_duration)
        card_content.add_widget(self.queue_info)

        # Progress bar with Spotify green - thicker for mobile
        self.progress_bar = MDProgressBar(
            value=0,
            size_hint_y=None,
            height=dp(6),
            color=[0.11, 0.73, 0.33, 1]
        )
        card_content.add_widget(self.progress_bar)

        # Time labels - larger for mobile
        time_box = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
        self.time_label = MDLabel(
            text="00:00 / 00:00",
            font_style="Body2",
            halign="center",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1]
        )
        time_box.add_widget(self.time_label)
        card_content.add_widget(time_box)

        now_playing_card.add_widget(card_content)
        main_content.add_widget(now_playing_card)

        # Stream download progress section (hidden by default) - larger for mobile
        self.stream_download_section = BoxLayout(size_hint_y=None, height=0, orientation='vertical', spacing=dp(8))
        self.stream_download_section.opacity = 0

        self.stream_download_title = MDLabel(
            text="Stream Download",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            size_hint_y=None,
            height=dp(28)
        )
        self.stream_download_progress_bar = MDProgressBar(
            value=0,
            size_hint_y=None,
            height=dp(6),
            color=[0.11, 0.73, 0.33, 1]
        )
        self.stream_download_status = MDLabel(
            text="",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            size_hint_y=None,
            height=dp(28)
        )

        self.stream_download_section.add_widget(self.stream_download_title)
        self.stream_download_section.add_widget(self.stream_download_progress_bar)
        self.stream_download_section.add_widget(self.stream_download_status)
        main_content.add_widget(self.stream_download_section)

        # File list with Spotify styling - larger for mobile
        file_list_header = MDLabel(
            text="Downloaded Songs",
            font_style="H5",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            size_hint_y=None,
            height=dp(48)
        )
        main_content.add_widget(file_list_header)

        self.file_list_layout = GridLayout(cols=1, spacing=dp(12), size_hint_y=None)
        self.file_list_layout.bind(minimum_height=self.file_list_layout.setter('height'))
        scroll_files = ScrollView()
        scroll_files.add_widget(self.file_list_layout)
        main_content.add_widget(scroll_files)

        # Logs section - larger for mobile
        log_header = MDLabel(
            text="Activity Log",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            size_hint_y=None,
            height=dp(40)
        )
        self.log_label = MDLabel(
            text="",
            size_hint_y=None,
            markup=True,
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
            font_style="Body2"
        )
        self.log_label.bind(texture_size=self._update_log_height)
        log_scroll = ScrollView(size_hint_y=None, height=dp(120))
        log_scroll.add_widget(self.log_label)

        main_content.add_widget(log_header)
        main_content.add_widget(log_scroll)

        # Wrap main content in scroll view
        main_scroll = ScrollView()
        main_scroll.add_widget(main_content)
        self.add_widget(main_scroll)

        # Bottom control bar (fixed at bottom, Spotify style) - larger for mobile
        bottom_bar = FloatLayout(size_hint_y=None, height=dp(100))

        with bottom_bar.canvas.before:
            Color(0.09, 0.09, 0.09, 1)
            self.bottom_rect = RoundedRectangle(size=(0, 0), pos=(0, 0), radius=[dp(0)])

        def update_bottom_rect(instance, value):
            self.bottom_rect.pos = bottom_bar.pos
            self.bottom_rect.size = bottom_bar.size

        bottom_bar.bind(size=update_bottom_rect, pos=update_bottom_rect)

        # Control buttons container - larger for mobile
        controls = BoxLayout(
            size_hint=(None, None),
            width=dp(340),
            height=dp(72),
            spacing=dp(20),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # Create icon buttons with larger size for mobile
        self.stop_btn = MDIconButton(
            icon="stop",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            icon_size=dp(40),
            on_press=self.stop_playback
        )
        self.pause_btn = MDIconButton(
            icon="pause",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            icon_size=dp(40),
            on_press=self.toggle_pause
        )
        self.skip_btn = MDIconButton(
            icon="skip-next",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            icon_size=dp(40),
            on_press=self.skip_song
        )
        self.queue_btn = MDIconButton(
            icon="playlist-music",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
            icon_size=dp(40),
            on_press=self.show_queue
        )

        controls.add_widget(self.stop_btn)
        controls.add_widget(self.pause_btn)
        controls.add_widget(self.skip_btn)
        controls.add_widget(self.queue_btn)

        bottom_bar.add_widget(controls)
        self.add_widget(bottom_bar)

    def show_download_progress(self):
        """Show the download progress section"""
        self.download_section.height = dp(70)
        self.download_section.opacity = 1

    def hide_download_progress(self):
        """Hide the download progress section"""
        self.download_section.height = 0
        self.download_section.opacity = 0
        self.download_progress_bar.value = 0
        self.download_status.text = ""

    def update_download_progress(self, value, status):
        """Update download progress"""
        self.download_progress_bar.value = value
        self.download_status.text = status

    def update_download_title(self, title):
        """Update download title"""
        self.download_title.text = title

    def show_stream_progress(self):
        """Show the stream download progress section"""
        self.stream_download_section.height = dp(50)
        self.stream_download_section.opacity = 1

    def hide_stream_progress(self):
        """Hide the stream download progress section"""
        self.stream_download_section.height = 0
        self.stream_download_section.opacity = 0
        self.stream_download_progress_bar.value = 0
        self.stream_download_status.text = ""

    def update_stream_progress(self, value, status):
        """Update stream download progress"""
        self.stream_download_progress_bar.value = value
        self.stream_download_status.text = status

    def cancel_download(self, instance=None):
        """Cancel the current download"""
        self.download_manager.cancel_download()

    def set_default_cover(self):
        """Set default cover art when no track is playing"""
        self.cover_art.source = ''
        self.cover_art.color = [0.3, 0.3, 0.3, 1]  # Dark gray background

    def update_cover_art(self, file_path=None, thumbnail_url=None):
        """Update cover art from file or URL"""
        cover_path = None

        if file_path and os.path.exists(file_path):
            # Try to extract cover art from audio file
            cover_path = extract_cover_art(file_path)

        if not cover_path and thumbnail_url:
            # Download cover art from URL
            cover_path = download_cover_art(thumbnail_url, filename=f"thumbnail_{abs(hash(thumbnail_url))}.jpg")

        if cover_path and os.path.exists(cover_path):
            self.cover_art.source = cover_path
            self.cover_art.color = [1, 1, 1, 1]
            try:
                self.cover_art.reload()
            except Exception:
                pass
        else:
            self.set_default_cover()

    def update_current_track(self, metadata, file_path=None):
        """Update current track information display and cover art"""
        try:
            self.track_title.text = metadata.get('title', 'Unknown Title')
            self.track_artist.text = f"Artist: {metadata.get('uploader', metadata.get('artist', 'Unknown Artist'))}"
            self.track_album.text = f"Album: {metadata.get('album', 'Unknown Album')}"

            # Display duration if available
            duration = metadata.get('duration')
            if duration:
                self.track_duration.text = f"Duration: {format_time(duration)}"
            else:
                self.track_duration.text = ""
        except Exception:
            pass

        # Update cover art
        thumbnail_url = metadata.get('thumbnail')
        self.update_cover_art(file_path, thumbnail_url)

    def update_queue_display(self, queue, current_index):
        """Update queue information display with total file size"""
        remaining = max(0, len(queue) - current_index - 1)

        # Calculate total size for remaining songs (excluding currently playing track)
        total_size_mb = 0
        for i in range(current_index + 1, len(queue)):
            entry = queue[i]
            # Estimate file size from duration (assuming ~1MB per minute for streaming quality)
            duration = entry.get('duration', 0)
            if duration:
                estimated_mb = (duration / 60) * 1.0
                total_size_mb += estimated_mb

        if total_size_mb > 0:
            if total_size_mb >= 1000:
                size_str = f"{total_size_mb / 1000:.1f} GB"
            else:
                size_str = f"{total_size_mb:.0f} MB"
            self.queue_info.text = f"Queue: {remaining} song(s) remaining (~{size_str})"
        else:
            self.queue_info.text = f"Queue: {remaining} song(s) remaining"

    def clear_queue_display(self):
        """Clear queue information when streaming ends"""
        self.queue_info.text = "Queue: 0 songs"

    def update_playback_progress(self, progress, current_time, total_time):
        """Update playback progress bar and time display"""
        self.progress_bar.value = min(progress, 100)
        self.time_label.text = f"{format_time(current_time)} / {format_time(total_time)}"

    def update_playback_state(self, state):
        """Update playback state (Playing/Paused)"""
        self.pause_btn.icon = "pause" if state == "Playing" else "play"

    def toggle_pause(self, _):
        """Toggle pause/resume for both stream and local playback"""
        if self.streamer.sound:
            # Toggle stream playback (check pause flag, not sound state)
            self.streamer.toggle_pause()
        elif self.current_sound:
            # Toggle local file playback (check pause flag, not sound state)
            self.toggle_local_pause()

    def toggle_local_pause(self):
        """Toggle pause for local files"""
        if self.local_is_paused:
            # Resume
            try:
                self.current_sound.play()
            except Exception:
                pass
            self.local_is_paused = False
            self.pause_btn.icon = "pause"
            if self.local_last_pause_time > 0:
                self.local_total_paused_time += time.time() - self.local_last_pause_time
                self.local_last_pause_time = 0
        else:
            # Pause
            try:
                self.current_sound.stop()
            except Exception:
                pass
            self.local_is_paused = True
            self.pause_btn.icon = "play"
            self.local_last_pause_time = time.time()

    def skip_song(self, _):
        """Skip the current song in stream"""
        if self.streamer.sound and getattr(self.streamer.sound, 'state', None) == 'play':
            self.streamer.skip()
        else:
            self.log("⚠️ No stream active to skip")

    def show_queue(self, _):
        """Show the current stream queue"""
        self.streamer.show_queue()

    def stop_playback(self, _):
        """Stop both stream and any currently playing audio"""
        self.streamer.stop()
        if self.current_sound:
            try:
                self.current_sound.stop()
                self.current_sound.unload()
            except Exception:
                pass
            self.current_sound = None
        self.log("⏹ Playback stopped")
        self.progress_bar.value = 0
        self.time_label.text = "00:00 / 00:00"
        self.local_is_paused = False
        self.local_last_pause_time = 0
        self.local_total_paused_time = 0
        self.set_default_cover()

    # ----- Logging -----
    def log(self, message):
        # Keep log from growing too large
        try:
            lines = self.log_label.text.split('\n') if self.log_label.text else []
            if len(lines) > 50:
                lines = lines[-40:]
            new_text = '\n'.join(lines) + (message + "\n")
            self.log_label.text = new_text
        except Exception:
            pass

    def _update_log_height(self, instance, size):
        try:
            self.log_label.height = max(size[1], self.log_label.height)
            self.log_label.text_size = (self.log_label.width, None)
        except Exception:
            pass

    # ----- File List -----
    def refresh_file_list(self):
        self.file_list_layout.clear_widgets()
        try:
            # Support multiple audio formats
            audio_extensions = ('.mp3', '.m4a', '.webm', '.opus', '.ogg')
            files = sorted(f for f in os.listdir(".") if f.lower().endswith(audio_extensions))
        except Exception:
            files = []

        for f in files:
            # Song card with Spotify styling - larger for mobile
            song_card = MDCard(
                size_hint_y=None,
                height=dp(88),
                md_bg_color=[0.09, 0.09, 0.09, 1],
                radius=[dp(8)],
                padding=dp(12)
            )

            card_layout = BoxLayout(spacing=dp(12))

            # Play button - larger for mobile
            play_btn = MDIconButton(
                icon="play-circle",
                theme_text_color="Custom",
                text_color=[0.11, 0.73, 0.33, 1],
                icon_size=dp(40),
                size_hint_x=None,
                width=dp(56)
            )
            play_btn.bind(on_press=lambda inst, file=f: self.play_audio(file))

            # File info (clickable for metadata)
            info_layout = BoxLayout(orientation='vertical', size_hint_x=0.7)
            file_label = MDLabel(
                text=f[:35] + "..." if len(f) > 35 else f,
                font_style="Body1",
                theme_text_color="Custom",
                text_color=[1, 1, 1, 1],
                font_size=dp(16)
            )
            info_btn = Button(
                text="",
                background_color=[0, 0, 0, 0],
                on_press=lambda inst, file=f: self.show_metadata(file)
            )
            info_layout.add_widget(file_label)

            # Convert button for convertible formats (m4a, opus)
            file_ext = os.path.splitext(f)[1].lower()
            if file_ext in ['.m4a', '.opus', '.ogg', '.webm']:
                convert_btn = MDIconButton(
                    icon="swap-horizontal",
                    theme_text_color="Custom",
                    text_color=[0.2, 0.6, 1.0, 1],
                    icon_size=dp(36),
                    size_hint_x=None,
                    width=dp(56)
                )
                convert_btn.bind(on_press=lambda inst, file=f: self.convert_audio(file))
                card_layout.add_widget(play_btn)
                card_layout.add_widget(info_layout)
                card_layout.add_widget(convert_btn)
            else:
                card_layout.add_widget(play_btn)
                card_layout.add_widget(info_layout)

            # Delete button - larger for mobile
            del_btn = MDIconButton(
                icon="delete",
                theme_text_color="Custom",
                text_color=[0.8, 0.2, 0.2, 1],
                icon_size=dp(36),
                size_hint_x=None,
                width=dp(56)
            )
            del_btn.bind(on_press=lambda inst, file=f: self.delete_audio(file))
            card_layout.add_widget(del_btn)

            song_card.add_widget(card_layout)
            self.file_list_layout.add_widget(song_card)

        self.file_list_layout.height = len(self.file_list_layout.children) * dp(100)

    def play_audio(self, file):
        if self.current_sound:
            try:
                self.current_sound.stop()
                self.current_sound.unload()
            except Exception:
                pass

        # Try to load the file, with automatic conversion if needed
        playable_file = file
        self.current_sound = SoundLoader.load(file)

        # If loading failed, try auto-conversion
        if not self.current_sound:
            self.log(f"⚠️ Cannot play {os.path.basename(file)} directly, attempting conversion...")
            converted_file = self.audio_converter.auto_convert_if_needed(file, self.log)
            if converted_file and converted_file != file:
                playable_file = converted_file
                self.current_sound = SoundLoader.load(converted_file)

        if self.current_sound:
            # Reset timing variables
            self.local_play_start_time = time.time()
            self.local_total_paused_time = 0
            self.local_last_pause_time = 0
            self.local_is_paused = False

            try:
                self.current_sound.play()
            except Exception:
                pass

            # Update track info and cover art
            metadata = get_metadata(playable_file)
            self.update_current_track(metadata, playable_file)

            # Start progress updates
            self.start_local_progress_updates()

            self.log(f"🎧 Now Playing: {os.path.basename(playable_file)}")
        else:
            self.log("❌ Failed to play audio. File format may be unsupported.")

    def start_local_progress_updates(self):
        """Start progress updates for locally played files"""
        self.stop_local_progress_updates()
        try:
            self.local_progress_event = Clock.schedule_interval(self.update_local_progress, 0.5)
        except Exception:
            self.local_progress_event = None

    def stop_local_progress_updates(self):
        """Stop local file progress updates"""
        if hasattr(self, 'local_progress_event') and self.local_progress_event:
            try:
                self.local_progress_event.cancel()
            except Exception:
                pass

    def update_local_progress(self, dt):
        """Update progress for locally playing files using manual timing"""
        if self.current_sound and getattr(self.current_sound, 'state', None) == 'play' and not self.local_is_paused:
            current_time = time.time() - self.local_play_start_time - self.local_total_paused_time
            duration = self.current_sound.length if getattr(self.current_sound, 'length', 0) > 0 else 1
            progress = (current_time / duration) * 100 if duration > 0 else 0

            self.progress_bar.value = progress
            self.time_label.text = f"{format_time(current_time)} / {format_time(duration)}"

    def show_metadata(self, file):
        """Show metadata for a file with cover art"""
        metadata = get_metadata(file)
        dialog = ModalView(size_hint=(0.8, 0.7))
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        layout.add_widget(Label(text="[b]Track Metadata[/b]", size_hint_y=0.1, font_size='16sp', markup=True))

        # Cover art in metadata dialog
        cover_path = extract_cover_art(file)
        if cover_path and os.path.exists(cover_path):
            cover_img = Image(
                source=cover_path,
                size_hint_y=0.3,
                allow_stretch=True,
                keep_ratio=True
            )
            layout.add_widget(cover_img)

        # Metadata details
        details_layout = BoxLayout(orientation='vertical', size_hint_y=0.4)
        details_layout.add_widget(Label(text=f"Title: {metadata['title']}", size_hint_y=0.25))
        details_layout.add_widget(Label(text=f"Artist: {metadata['artist']}", size_hint_y=0.25))
        details_layout.add_widget(Label(text=f"Album: {metadata['album']}", size_hint_y=0.25))
        details_layout.add_widget(Label(text=f"File: {file}", size_hint_y=0.25))
        layout.add_widget(details_layout)

        close_btn = Button(text="Close", size_hint_y=0.1)
        close_btn.bind(on_press=lambda x: dialog.dismiss())
        layout.add_widget(close_btn)

        dialog.add_widget(layout)
        dialog.open()

    def convert_audio(self, file):
        """Manually convert an audio file to MP3"""
        def do_conversion():
            converted_file = self.audio_converter.convert_to_mp3(file, log_callback=self.log)
            if converted_file and os.path.exists(converted_file):
                Clock.schedule_once(lambda dt: self.refresh_file_list())
            else:
                Clock.schedule_once(lambda dt: self.log(f"❌ Conversion failed for {os.path.basename(file)}"))

        # Run conversion in background thread
        threading.Thread(target=do_conversion, daemon=True).start()

    def delete_audio(self, file):
        """Delete an audio file"""
        try:
            # Also delete cached cover art
            cover_path = extract_cover_art(file)
            if cover_path and os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                except Exception:
                    pass

            os.remove(file)
            self.log(f"🗑️ Deleted: {file}")
            self.refresh_file_list()
        except Exception as e:
            self.log(f"❌ Error deleting {file}: {e}")

    # ----- Download -----
    def start_download(self, _):
        url = self.url_input.text.strip()
        if not url:
            self.log("⚠️ Please enter a link.")
            return
        self.download_manager.start_download(url)

    # ----- Stream -----
    def start_stream(self, _):
        url = self.url_input.text.strip()
        if not url:
            self.log("⚠️ Please enter a playlist URL.")
            return
        self.log("📡 Starting stream...")
        threading.Thread(target=self.streamer.stream_playlist, args=(url,), daemon=True).start()


# ------------------- App Entry -------------------
class AudioApp(MDApp):
    def build(self):
        self.title = "🎵 Music Player"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.primary_hue = "A700"
        self.theme_cls.accent_palette = "Green"
        return DownloaderUI()


if __name__ == "__main__":
    try:
        AudioApp().run()
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
