import os
import logging
import subprocess
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TCON, APIC
from modules.constants import FOLDER_PATHS

def process_audio_files(folder, config, processed_list):
    genre = config['AUDIO PROCESSING']['ID3_GENRE_OVERWRITE']
    bitrate = config['AUDIO PROCESSING']['OUTPUT_BITRATE']
    for file in os.listdir(folder):
        if file.lower().endswith(('.mp3', '.wav', '.flac', '.aac', '.m4a')):
            original = os.path.join(folder, file)
            base = os.path.splitext(file)[0]
            out_path = os.path.join(FOLDER_PATHS['sftp'], f"{base}.mp3")
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", original, "-codec:a", "libmp3lame",
                    "-b:a", bitrate, out_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                audio = MP3(out_path, ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
                else:
                    audio.tags.clear()

                artist, title = base.split("-", 1) if "-" in base else (base, "")
                audio.tags.add(TPE1(encoding=3, text=artist.strip()))
                audio.tags.add(TIT2(encoding=3, text=title.strip()))
                audio.tags.add(TCON(encoding=3, text=genre))

                # Embed album art if available
                for art_file in os.listdir(folder):
                    if art_file.startswith("album_art") and art_file.endswith(('.jpg', '.jpeg', '.png')):
                        art_path = os.path.join(folder, art_file)
                        with open(art_path, 'rb') as img:
                            audio.tags.add(APIC(
                                encoding=3,
                                mime="image/jpeg",
                                type=3,
                                desc="Cover",
                                data=img.read()
                            ))
                        break

                audio.save()
                processed_list.append(f"{base}.mp3")
                logging.info(f"Processed & tagged audio: {file}")
                return True
            except Exception as e:
                logging.error(f"Audio processing failed for {file}: {e}")
    return False
