# Audio Fingerprinting (Shazam-style) Implementation Plan

This project implements a classic landmark-based audio fingerprinting system (similar to the Shazam algorithm) in Python. The system indexes a library of audio tracks into a database of hashes and identifies short, noisy query clips by matching their hashes and finding the consensus alignment offset.

---

## Proposed System Architecture

We will organize the codebase into clean modules:

1. **`fingerprinter.py`**: Core algorithm code (STFT, peak detection, hash generation, database search, matching logic).
2. **`index_songs.py`**: A CLI utility to scan a folder of audio files, extract fingerprints, and save them into a database file (`fingerprints_db.pkl`).
3. **`app.py`**: The Streamlit user interface featuring three tabs:
   - **Library View**: Display indexed songs and metadata.
   - **Single-Clip Mode**: Upload an audio file, display its spectrogram, constellation of peaks, offset histogram of the match, and show candidate scores.
   - **Batch Mode**: Upload a ZIP file or select multiple audio clips to run a batch classification and export a standard `results.csv`.
4. **`audio_fingerprinting.ipynb`**: A Jupyter Notebook designed to run on Google Colab to index the database, run parameter experiments (window lengths, paired hashes vs. single peaks, noise resistance, pitch/time transformations), and plot the outputs required for the report.
5. **`requirements.txt`**: Package declarations.

---

## Core Algorithm Specifications

### 1. Feature Extraction (Spectrogram to Constellation)
- **Audio Loading**: Load audio using `librosa` or `scipy.io.wavfile` at a standardized sampling rate (e.g., $22050\text{ Hz}$).
- **Spectrogram**: Compute the Short-Time Fourier Transform (STFT) with custom window length (e.g., $1024$ or $2048$ samples) and hop size (e.g., $512$ samples).
- **Peak Finding (Constellation Map)**:
  - Find local peaks in the magnitude spectrogram (frequency-time plane) using a 2D local maximum filter (via `scipy.ndimage.maximum_filter`).
  - Filter out weaker peaks, keeping a density of approximately $30-50$ peaks per second of audio.
  - This forms the *constellation map* (coordinates of $(t, f)$ peaks).

### 2. Fingerprinting (Hashing)
- **Single Peaks vs. Paired Hashes**:
  - *Single Peaks*: Hash is just the frequency of the peak: $H = f$.
  - *Paired Hashes*: Pair an anchor peak $(t_1, f_1)$ with target peaks $(t_2, f_2)$ in a designated "target zone" ahead in time: $t_1 + \Delta t_{min} \le t_2 \le t_1 + \Delta t_{max}$.
  - The hash key is a combination of the frequencies and the time difference: $H = \text{hash}(f_1, f_2, t_2 - t_1)$.
  - The value stored is the anchor time $t_1$ and the song identifier: $(song\_id, t_1)$.

### 3. Database Matching
- **Lookups**: For each hash generated from the query clip, find matches in the database.
- **Offset Calculation**: For each match, compute the alignment offset:
  $$\Delta t = t_{\text{song}} - t_{\text{clip}}$$
- **Scoring**: Count matches per $(song\_id, \Delta t)$.
- **Offset Histogram**: Plot the distribution of $\Delta t$ offsets for each candidate song. A correct match will show a sharp peak at a single offset, whereas an incorrect match will show scattered, random matches.
- **Decision**: The candidate song with the highest offset match count (exceeding a threshold) is predicted.

### 4. Database Schema & Size Optimization
To stay within Streamlit Community Cloud RAM limits (< 1 GB) and GitHub's 100 MB file limit, the SQLite schema is optimized for integer hashing:
- **Hash Key Packing**: In `'pairs'` mode, each tuple of `(freq_anchor, freq_target, delta_time)` is packed into a single 32-bit integer `h_val` using bitwise shifts:
  $$\text{hash\_key} = (f_1 \ll 18) \mid (f_2 \ll 8) \mid dt$$
  where $f_1, f_2 \le 1024$ (fits in 10 bits each since $N_{\text{fft}} = 2048$), and $dt \le 150$ (fits in 8 bits).
- **Index Optimization**: Storing `hash_key` as an `INTEGER` instead of `TEXT` reduces database size by over 30% and keeps the B-Tree index extremely compact, bringing the compressed repository size under 45 MB.

---

## Proposed Components

### 1. `fingerprinter.py`
Contains:
- `load_audio(filepath, target_sr=22050)`
- `compute_spectrogram(y, sr, n_fft, hop_length)`
- `find_peaks(spectrogram, neighborhood_size, threshold)`
- `generate_hashes(peaks, min_delta_t, max_delta_t, fan_value)`
- `index_song(filepath, db)`
- `match_clip(clip_hashes, db)`

### 2. `index_songs.py`
Contains:
- Command-line tool to initialize/update `fingerprints_db.pkl` from a directory of audio files.

### 3. `app.py`
A Streamlit web interface with a dark visual design:
- Interactive plots using `matplotlib` / `plotly` for visual analysis.
- Dropdown or sidebar instructions.
- File upload fields for query clips.

### 4. `audio_fingerprinting.ipynb`
Jupyter Notebook divided into clear sections:
- **Environment Setup**: Install packages (`librosa`, `scipy`, etc.).
- **Core Implementation**: Copy of algorithm code.
- **Database Building**: Code to build the database from a folder on Google Drive.
- **Experiments & Plots**:
  1. Window length comparison (effect of spectrogram resolution on matching).
  2. Single peaks vs. Paired hashes (demonstrating why pairing makes matches much more decisive).
  3. Noise Robustness (adding Gaussian white noise at different SNR levels and plotting accuracy).
  4. Pitch Shift & Time Stretch (applying audio pitch/time transformations and examining recognition limits).

---

## Verification Plan

### Automated Checks
- Mock database with simulated audio inputs to verify that the hashing and matching routines compute offsets and identify the correct file correctly.
- Test suite verifying exact output format of `results.csv` in batch mode.

### Manual Verification
- Run Streamlit locally (`streamlit run app.py`).
- Inspect the visual steps (spectrogram, constellation, offset histogram) on sample test clips.
