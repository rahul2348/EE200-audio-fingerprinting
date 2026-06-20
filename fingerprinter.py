import os
import sqlite3
import json
import numpy as np
import scipy.signal
import scipy.ndimage
import librosa

# Default configuration parameters
DEFAULT_FS = 22050          # Standard sampling rate (Hz)
DEFAULT_NFFT = 2048         # STFT window length
DEFAULT_HOP = 512           # STFT hop size (overlap = 75%)
MIN_PEAK_DIST = 10          # Minimum separation between peaks in 2D grid
PEAK_PERCENTILE = 85        # Amplitude threshold percentile for peak selection
FAN_VALUE = 15              # Fan-out value: max number of target peaks for each anchor
MIN_DELTA_T = 0             # Min time difference between anchor and target (in frames)
MAX_DELTA_T = 150           # Max time difference between anchor and target (in frames)

def load_audio(filepath, target_sr=DEFAULT_FS, duration=None):
    """
    Load an audio file and resample to target sampling rate.
    Can be truncated using the duration parameter (in seconds).
    """
    try:
        y, sr = librosa.load(filepath, sr=target_sr, duration=duration)
        return y, sr
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None, None

def compute_spectrogram(y, sr, n_fft=DEFAULT_NFFT, hop_length=DEFAULT_HOP):
    """
    Compute log-amplitude spectrogram of the audio signal.
    """
    # Short-Time Fourier Transform
    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    S = np.abs(D)
    
    # Avoid zero division and apply log scaling
    log_S = librosa.amplitude_to_db(S, ref=np.max)
    return log_S

def get_peaks(spectrogram, min_dist=MIN_PEAK_DIST, percentile=PEAK_PERCENTILE):
    """
    Find local peaks in the 2D spectrogram using a local maximum filter.
    Returns:
        List of tuples (time_idx, freq_idx)
    """
    # 2D maximum filter
    # neighborhood of size (2*min_dist + 1)
    size = 2 * min_dist + 1
    local_max = (spectrogram == scipy.ndimage.maximum_filter(spectrogram, size=(size, size)))
    
    # Apply amplitude thresholding (keep only top percentile of magnitudes)
    thresh = np.percentile(spectrogram, percentile)
    detected_peaks = local_max & (spectrogram > thresh)
    
    # Get coordinates of peaks
    time_idxs, freq_idxs = np.where(detected_peaks)
    
    # Zip coordinates and return as list of tuples (cast to native Python int for JSON serialization)
    peaks = [(int(t), int(f)) for t, f in zip(time_idxs, freq_idxs)]
    return peaks

def generate_hashes(peaks, mode='pairs', fan_value=FAN_VALUE, min_delta=MIN_DELTA_T, max_delta=MAX_DELTA_T):
    """
    Generate hashes from constellation map peaks.
    If mode == 'pairs':
        Shazam-style paired hashes: ((freq_anchor, freq_target, delta_time), time_anchor)
    If mode == 'single':
        Single peak hashes: ((freq_anchor,), time_anchor)
    """
    hashes = []
    num_peaks = len(peaks)
    
    # Sort peaks by time index to facilitate looking forward in time
    peaks = sorted(peaks, key=lambda x: x[0])
    
    if mode == 'single':
        for t, f in peaks:
            hashes.append(((f,), t))
        return hashes
        
    for i in range(num_peaks):
        t1, f1 = peaks[i]
        
        # Look at subsequent peaks in time (target zone)
        count = 0
        for j in range(i + 1, num_peaks):
            t2, f2 = peaks[j]
            dt = t2 - t1
            
            # Check if within target zone
            if min_delta <= dt <= max_delta:
                # Key: (freq_anchor, freq_target, time_difference)
                # Value: time_anchor
                hashes.append(((f1, f2, dt), t1))
                count += 1
                if count >= fan_value:
                    break
            elif dt > max_delta:
                # Since peaks are sorted by time, we can stop searching once dt exceeds max_delta
                break
                
    return hashes

class SongPeaksDict:
    """
    Helper dict-like object to lazily fetch song peaks from SQLite.
    This avoids loading all peaks for all songs into memory on startup.
    """
    def __init__(self, db):
        self.db = db
        
    def __contains__(self, song_idx):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM songs")
        count = cursor.fetchone()[0]
        cursor.close()
        return 0 <= song_idx < count
        
    def __getitem__(self, song_idx):
        # Fetch the peaks for the song at index song_idx (ordered by ID)
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, peaks FROM songs ORDER BY id LIMIT 1 OFFSET ?", (song_idx,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            song_id, peaks_json = row
            if peaks_json:
                raw_peaks = json.loads(peaks_json)
                return [tuple(p) for p in raw_peaks]
            return []
        raise KeyError(song_idx)

class FingerprintDatabase:
    def __init__(self, db_path, mode='pairs'):
        self.db_path = db_path
        self.mode = mode
        
        # Streamlit runs multi-threaded, so check_same_thread=False is mandatory
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        
        # Cache song index and peaks helper
        self.song_peaks = SongPeaksDict(self)
        self._refresh_songs_cache()
        
    def _init_db(self):
        cursor = self.conn.cursor()
        # Create metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Create songs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                peaks TEXT
            )
        """)
        # Create fingerprints table (hash_key is INTEGER for optimization)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fingerprints (
                hash_key INTEGER,
                song_id INTEGER,
                time_offset INTEGER,
                FOREIGN KEY(song_id) REFERENCES songs(id)
            )
        """)
        
        # Create indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints(hash_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_song ON fingerprints(song_id)")
        
        # Initialize mode in database metadata if not already present
        cursor.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('mode', ?)", (self.mode,))
        self.conn.commit()
        
        # Load mode from metadata to ensure consistency with existing databases
        cursor.execute("SELECT value FROM metadata WHERE key='mode'")
        row = cursor.fetchone()
        if row:
            self.mode = row[0]
        cursor.close()
            
    def _refresh_songs_cache(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM songs ORDER BY id")
        self.songs = [row[0] for row in cursor.fetchall()]
        self._song_name_to_idx = {name: idx for idx, name in enumerate(self.songs)}
        cursor.close()
        
    def get_hash_count(self, song_idx):
        """
        Count hashes for a song at index song_idx.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM songs ORDER BY id LIMIT 1 OFFSET ?", (song_idx,))
        row = cursor.fetchone()
        count = 0
        if row:
            song_id = row[0]
            cursor.execute("SELECT COUNT(*) FROM fingerprints WHERE song_id=?", (song_id,))
            count = cursor.fetchone()[0]
        cursor.close()
        return count
        
    def add_song(self, song_name, hashes, peaks=None):
        peaks_json = json.dumps(peaks) if peaks is not None else None
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO songs (name, peaks) VALUES (?, ?)", (song_name, peaks_json))
            song_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # Song already exists, retrieve ID
            cursor.execute("SELECT id FROM songs WHERE name=?", (song_name,))
            song_id = cursor.fetchone()[0]
            print(f"Song '{song_name}' is already indexed. Re-indexing hashes...")
            # Optional: delete existing hashes for this song to avoid duplicates
            cursor.execute("DELETE FROM fingerprints WHERE song_id=?", (song_id,))
            
        # Prepare bulk inserts
        fingerprint_rows = []
        for h_key, t_anchor in hashes:
            if self.mode == 'pairs':
                # Pack (f1, f2, dt) into a single 32-bit integer
                # f1 and f2 fit in 10 bits (<1024), dt fits in 8 bits (<256)
                f1, f2, dt = h_key
                h_val = (f1 << 18) | (f2 << 8) | dt
            else:
                h_val = h_key[0]
            fingerprint_rows.append((h_val, song_id, t_anchor))
            
        # Bulk insert
        cursor.executemany(
            "INSERT INTO fingerprints (hash_key, song_id, time_offset) VALUES (?, ?, ?)",
            fingerprint_rows
        )
        self.conn.commit()
        cursor.close()
        self._refresh_songs_cache()
        
    def save(self, filepath):
        # Commit and close/reopen connection to flush database to disk
        self.conn.commit()
        print(f"Database saved to {filepath} successfully.")
        
    def close(self):
        self.conn.close()
        
    @staticmethod
    def load(filepath):
        # Simply instantiate the database object pointing to the file path
        return FingerprintDatabase(filepath)

def match_query(query_hashes, db):
    """
    Search for matches of query clip hashes in the SQLite database.
    Returns:
        matches: Dictionary of matches grouped by song index, containing offsets.
        sorted_candidates: List of candidates sorted by match count.
    """
    # Group query hashes by key to perform batch searches
    key_to_tclip = {}
    for h_key, t_clip in query_hashes:
        if db.mode == 'pairs':
            # Pack (f1, f2, dt) into a single 32-bit integer
            f1, f2, dt = h_key
            h_val = (f1 << 18) | (f2 << 8) | dt
        else:
            h_val = h_key[0]
            
        if h_val not in key_to_tclip:
            key_to_tclip[h_val] = []
        key_to_tclip[h_val].append(t_clip)
        
    matches = {}
    h_vals = list(key_to_tclip.keys())
    
    # Query in batches of 900 to stay under SQLite parameter limits
    cursor = db.conn.cursor()
    batch_size = 900
    for idx in range(0, len(h_vals), batch_size):
        batch = h_vals[idx : idx + batch_size]
        placeholders = ",".join(["?"] * len(batch))
        
        # Join fingerprints with songs table to get song names
        cursor.execute(f"""
            SELECT f.hash_key, s.name, f.time_offset
            FROM fingerprints f
            JOIN songs s ON f.song_id = s.id
            WHERE f.hash_key IN ({placeholders})
        """, batch)
        
        # Accumulate matches
        for hash_key, song_name, t_song in cursor.fetchall():
            song_idx = db._song_name_to_idx.get(song_name)
            if song_idx is None:
                continue
                
            h_val_db = int(hash_key)
            for t_clip in key_to_tclip[h_val_db]:
                offset = t_song - t_clip
                if song_idx not in matches:
                    matches[song_idx] = []
                matches[song_idx].append(offset)
    cursor.close()
                
    # Evaluate consensus alignment for each candidate
    candidate_scores = []
    for song_idx, offsets in matches.items():
        if len(offsets) == 0:
            continue
            
        # Find the highest peak in the offset histogram (consensus alignment)
        offset_counts = {}
        for off in offsets:
            offset_counts[off] = offset_counts.get(off, 0) + 1
            
        best_offset = max(offset_counts, key=offset_counts.get)
        max_matches = offset_counts[best_offset]
        
        candidate_scores.append({
            'song_idx': song_idx,
            'song_name': db.songs[song_idx],
            'total_matches': len(offsets),
            'consensus_matches': max_matches,
            'best_offset': best_offset,
            'offset_counts': offset_counts
        })
        
    # Sort candidates by consensus matches in descending order
    sorted_candidates = sorted(candidate_scores, key=lambda x: x['consensus_matches'], reverse=True)
    return matches, sorted_candidates
