import os
import sys
import argparse
import fingerprinter

def index_directory(song_dir, db_path, mode='pairs'):
    print(f"Indexing songs in directory: {song_dir}")
    print(f"Mode: {mode}")
    
    # Initialize database
    db = fingerprinter.FingerprintDatabase(db_path, mode=mode)
    
    # Scan for audio files
    supported_extensions = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aiff')
    audio_files = []
    for root, _, files in os.walk(song_dir):
        for file in files:
            if file.lower().endswith(supported_extensions):
                audio_files.append(os.path.join(root, file))
                
    if not audio_files:
        print(f"No supported audio files found in {song_dir}")
        return
        
    print(f"Found {len(audio_files)} audio files to index.")
    
    for idx, filepath in enumerate(audio_files):
        filename = os.path.basename(filepath)
        song_name, _ = os.path.splitext(filename)
        
        print(f"[{idx+1}/{len(audio_files)}] Processing {filename}...")
        
        # Load audio
        y, sr = fingerprinter.load_audio(filepath)
        if y is None:
            print(f"Failed to load {filename}, skipping.")
            continue
            
        # Compute spectrogram
        spectrogram = fingerprinter.compute_spectrogram(y, sr)
        
        # Get peaks
        peaks = fingerprinter.get_peaks(spectrogram)
        
        # Generate hashes
        hashes = fingerprinter.generate_hashes(peaks, mode=mode)
        
        # Add to database
        db.add_song(song_name, hashes, peaks=peaks)
        print(f"Successfully indexed {song_name} with {len(hashes)} hashes.")
        
    # Save database
    db.save(db_path)
    db.close() # Close connection
    print(f"Indexing complete. Database saved to {db_path}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index a folder of songs for audio fingerprinting.")
    parser.add_argument("song_dir", help="Path to the directory containing song audio files")
    parser.add_argument("--db", default="fingerprints_db.db", help="Output database file path (default: fingerprints_db.db)")
    parser.add_argument("--mode", default="pairs", choices=["pairs", "single"], help="Indexing mode: 'pairs' for paired hashes, 'single' for single peaks (default: pairs)")
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.song_dir):
        print(f"Error: {args.song_dir} is not a valid directory.")
        sys.exit(1)
        
    index_directory(args.song_dir, args.db, args.mode)
