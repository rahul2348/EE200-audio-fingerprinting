import os
import wave
import struct
import math
import random

def generate_tone_wav(filepath, duration_sec, base_freqs, sr=22050):
    """
    Generate a mono 16-bit WAV file with pulsed note changes.
    Each note step (every 0.5s) consists of 0.15s of chord tones followed by 0.35s of silence.
    This creates sharp onsets which lock peak coordinates in time.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with wave.open(filepath, 'w') as f:
        f.setnchannels(1)  # Mono
        f.setsampwidth(2)  # 16-bit
        f.setframerate(sr)
        
        num_samples = int(duration_sec * sr)
        for i in range(num_samples):
            t = i / sr
            
            # Determine step (every 0.5 seconds)
            step = int(t / 0.5)
            in_step_time = t % 0.5
            
            # 0.15s sound, 0.35s silence
            if in_step_time < 0.15:
                # Melodic scale factor based on step
                melodic_scale = [1.0, 1.2, 1.25, 1.33, 1.5, 1.66, 1.875, 2.0]
                mult = melodic_scale[step % len(melodic_scale)]
                
                # Apply amplitude envelope (fade in/out slightly to avoid clicks but keep onset sharp)
                envelope = 1.0
                if in_step_time < 0.02:
                    envelope = in_step_time / 0.02
                elif in_step_time > 0.13:
                    envelope = (0.15 - in_step_time) / 0.02
                
                val = 0
                for idx, base_f in enumerate(base_freqs):
                    freq = base_f * mult
                    val += math.sin(2 * math.pi * freq * t)
                val = (val / len(base_freqs)) * envelope if base_freqs else 0
            else:
                val = 0.0
            
            # Clip and pack
            val = max(-1.0, min(1.0, val))
            val_int = int(val * 32767)
            data = struct.pack('<h', val_int)
            f.writeframesraw(data)

def generate_clip_with_offset(song_filepath, clip_filepath, start_sec, duration_sec, noise_level=0.0, sr=22050):
    """
    Extract a slice of an existing WAV file, optionally add noise, and save as a new WAV.
    """
    os.makedirs(os.path.dirname(clip_filepath), exist_ok=True)
    
    with wave.open(song_filepath, 'rb') as f_in:
        params = f_in.getparams()
        sampwidth = f_in.getsampwidth()
        framerate = f_in.getframerate()
        
        # Calculate frame boundaries
        start_frame = int(start_sec * framerate)
        num_frames = int(duration_sec * framerate)
        
        f_in.setpos(start_frame)
        frames = f_in.readframes(num_frames)
        
    # Unpack samples to add noise if required
    num_samples = len(frames) // sampwidth
    unpacked = list(struct.unpack(f'<{num_samples}h', frames))
    
    # Process samples
    processed = []
    for val_int in unpacked:
        val = val_int / 32767.0
        if noise_level > 0:
            val += random.gauss(0, noise_level)
        val = max(-1.0, min(1.0, val))
        processed.append(int(val * 32767))
        
    # Write clip
    with wave.open(clip_filepath, 'w') as f_out:
        f_out.setparams(params)
        f_out.writeframes(struct.pack(f'<{num_samples}h', *processed))

def main():
    print("Generating mock audio files with sharp temporal onsets...")
    
    # 1. Generate full library tracks (30 seconds each)
    songs_dir = "./songs_library"
    print("Writing library songs...")
    
    # Song A: A major based pulsed melody
    generate_tone_wav(
        os.path.join(songs_dir, "The_Long_And_Winding_Road.wav"),
        duration_sec=30.0,
        base_freqs=[220.0, 277.18, 329.63]
    )
    
    # Song B: C major based pulsed melody
    generate_tone_wav(
        os.path.join(songs_dir, "Two_Of_Us.wav"),
        duration_sec=30.0,
        base_freqs=[261.63, 329.63, 392.00]
    )
    
    # Song C: D minor based pulsed melody
    generate_tone_wav(
        os.path.join(songs_dir, "Within_You_Without_You.wav"),
        duration_sec=30.0,
        base_freqs=[293.66, 349.23, 440.00]
    )
    
    # 2. Extract query clips (10 seconds each)
    samples_dir = "./samples"
    print("Writing query samples...")
    
    # Sample 1: Clean slice of Song A starting at 12.0 seconds
    generate_clip_with_offset(
        os.path.join(songs_dir, "The_Long_And_Winding_Road.wav"),
        os.path.join(samples_dir, "sample1.wav"),
        start_sec=12.0,
        duration_sec=10.0,
        noise_level=0.0
    )
    
    # Sample 2: Noisy slice of Song B starting at 5.0 seconds
    generate_clip_with_offset(
        os.path.join(songs_dir, "Two_Of_Us.wav"),
        os.path.join(samples_dir, "sample2.wav"),
        start_sec=5.0,
        duration_sec=10.0,
        noise_level=0.05 # Add low Gaussian noise
    )
    
    print("Done! Mock files created successfully.")

if __name__ == "__main__":
    main()
