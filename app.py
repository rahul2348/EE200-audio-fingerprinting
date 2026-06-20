import os
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import fingerprinter
from fingerprinter import FingerprintDatabase
import zipfile
import io

# Page Configuration
st.set_page_config(
    page_title="EE200: Audio Fingerprinting",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    /* Dark theme styling override */
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    /* Title and Subtitle */
    .app-title {
        font-size: 36px;
        font-weight: 800;
        color: #FAFAFA;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .app-subtitle {
        font-size: 14px;
        color: #A0AEC0;
        margin-bottom: 24px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Tabs customization */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 1px solid #2D3748;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        padding: 8px 16px;
        font-size: 15px;
        font-weight: 600;
        color: #718096;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        color: #00D2C4 !important;
        border-bottom: 2px solid #00D2C4 !important;
    }
    
    /* Card design for indexed songs */
    .song-card {
        background-color: #1A202C;
        border: 1px solid #2D3748;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .song-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0, 210, 196, 0.15);
        border-color: #00D2C4;
    }
    .song-card-title {
        font-size: 17px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 6px;
    }
    .song-card-meta {
        font-size: 13px;
        color: #A0AEC0;
    }
    
    /* Info box design */
    .custom-info {
        background-color: #1A202C;
        border-left: 4px solid #00D2C4;
        padding: 16px;
        border-radius: 4px;
        margin-bottom: 20px;
    }
    
    /* Custom button behavior */
    .stButton>button {
        background-color: #00D2C4;
        color: #0E1117;
        font-weight: 700;
        border-radius: 8px;
        border: none;
        padding: 8px 24px;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #05F2E3;
        box-shadow: 0 0 15px rgba(0, 210, 196, 0.4);
        color: #0E1117;
    }
    
    /* Header decoration */
    .section-header {
        font-size: 18px;
        font-weight: 700;
        color: #00D2C4;
        margin-top: 24px;
        margin-bottom: 12px;
        border-bottom: 1px solid #2D3748;
        padding-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Layout Title
st.markdown("""
<div class="app-title">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#00D2C4" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2v20M17 5v14M22 8v8M7 8v8M2 10v4"/>
    </svg>
    EE200: Audio Fingerprinting
</div>
<div class="app-subtitle">Signals, Systems & Networks &bull; Project</div>
""", unsafe_allow_html=True)

# Helper function to load DB
@st.cache_resource
def load_db(path, mtime):
    if os.path.exists(path):
        try:
            return fingerprinter.FingerprintDatabase.load(path)
        except Exception as e:
            st.error(f"Error loading database: {e}")
            return None
    return None

# Load Database
DB_FILE = "fingerprints_db.db"
DB_XZ_FILE = "fingerprints_db.db.xz"

# Auto-decompress database if xz file exists but uncompressed db doesn't
if not os.path.exists(DB_FILE) and os.path.exists(DB_XZ_FILE):
    with st.spinner("Extracting optimized database on first run..."):
        try:
            import lzma
            with lzma.open(DB_XZ_FILE, "rb") as f_in:
                with open(DB_FILE, "wb") as f_out:
                    while True:
                        chunk = f_in.read(1024 * 1024)  # 1MB chunk
                        if not chunk:
                            break
                        f_out.write(chunk)
            st.success("Database extracted successfully!")
        except Exception as e:
            st.error(f"Failed to decompress database: {e}")

db_exists = os.path.exists(DB_FILE)
st.sidebar.markdown("### Database Debug Info")
st.sidebar.write(f"File exists: `{db_exists}`")
if db_exists:
    st.sidebar.write(f"File size: `{os.path.getsize(DB_FILE) / 1024 / 1024:.2f} MB`")
    db_mtime = os.path.getmtime(DB_FILE)
    try:
        db = load_db(DB_FILE, db_mtime)
        st.sidebar.write(f"Loaded object: `{type(db)}`")
        if db is not None:
            st.sidebar.write(f"Indexed songs count: `{len(db.songs)}`")
    except Exception as ex:
        st.sidebar.error(f"Failed loading DB: {ex}")
        db = None
else:
    db = None

# Tabs Navigation
tab_library, tab_identify, tab_batch = st.tabs(["LIBRARIES", "IDENTIFY", "BATCH"])

# ----------------- TAB 1: LIBRARY -----------------
with tab_library:
    st.markdown("<div class='section-header'>Indexed Audio Library</div>", unsafe_allow_html=True)
    
    if db is None:
        st.markdown(f"""
        <div class="custom-info">
            <strong>Database Not Found!</strong><br>
            No fingerprint database was found at <code>{DB_FILE}</code>. 
            To get started, you can build a database by using the form below or running the indexer script.
        </div>
        """, unsafe_allow_html=True)
        
        # Admin builder form
        with st.expander("Create New Fingerprint Database"):
            song_dir = st.text_input("Local Songs Directory Path", value="./songs_library")
            mode = st.selectbox("Indexing Mode", ["pairs", "single"], index=0, 
                                help="'pairs' creates robust time-frequency pairs (Shazam), 'single' indexes solo peaks.")
            
            if st.button("Index Directory"):
                if not os.path.isdir(song_dir):
                    st.error(f"The path '{song_dir}' is not a valid directory.")
                else:
                    with st.spinner("Scanning and indexing files..."):
                        import index_songs
                        try:
                            index_songs.index_directory(song_dir, DB_FILE, mode=mode)
                            st.success("Indexing completed successfully!")
                            st.cache_resource.clear()
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Indexing failed: {ex}")
    else:
        st.info(f"Database loaded successfully in **{db.mode.upper()}** mode. It contains **{len(db.songs)}** songs.")
        
        # Grid of songs
        cols = st.columns(3)
        for i, song_name in enumerate(db.songs):
            col = cols[i % 3]
            
            # Count hashes for this song
            song_hash_count = db.get_hash_count(i)
                        
            # Format the card
            with col:
                st.markdown(f"""
                <div class="song-card">
                    <div class="song-card-title">{song_name}</div>
                    <div class="song-card-meta">{song_hash_count:,} hashes</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Tiny constellation preview
                if i in db.song_peaks:
                    peaks = db.song_peaks[i]
                    if len(peaks) > 0:
                        peaks_arr = np.array(peaks)
                        fig, ax = plt.subplots(figsize=(4, 0.8), facecolor='#1A202C')
                        ax.set_facecolor('#1A202C')
                        ax.scatter(peaks_arr[:, 0] * fingerprinter.DEFAULT_HOP / fingerprinter.DEFAULT_FS, 
                                   peaks_arr[:, 1] * fingerprinter.DEFAULT_FS / fingerprinter.DEFAULT_NFFT, 
                                   s=1, c='#00D2C4', alpha=0.6)
                        ax.axis('off')
                        st.pyplot(fig)
                        plt.close(fig)

# ----------------- TAB 2: IDENTIFY -----------------
with tab_identify:
    st.markdown("<div class='section-header'>Identify a Clip</div>", unsafe_allow_html=True)
    
    if db is None:
        st.warning("Please index or upload a fingerprint database in the LIBRARY tab before searching.")
    else:
        # File uploader
        uploaded_file = st.file_uploader("Upload an audio clip to identify", type=["wav", "mp3", "flac", "ogg", "m4a"])
        
        # OR Try a Sample
        samples_dir = "./samples"
        sample_clips = []
        if os.path.exists(samples_dir):
            sample_clips = [f for f in os.listdir(samples_dir) if f.lower().endswith(('.wav', '.mp3'))]
            
        selected_sample = None
        if sample_clips:
            st.write("Or try a sample:")
            cols_samples = st.columns(len(sample_clips))
            for s_idx, sample_name in enumerate(sample_clips):
                with cols_samples[s_idx]:
                    if st.button(f"Try {sample_name}"):
                        selected_sample = os.path.join(samples_dir, sample_name)
        
        # Process clip if uploaded or selected
        target_clip = None
        clip_name = None
        if uploaded_file is not None:
            target_clip = uploaded_file
            clip_name = uploaded_file.name
        elif selected_sample is not None:
            target_clip = selected_sample
            clip_name = os.path.basename(selected_sample)
            
        if target_clip is not None:
            st.audio(target_clip)
            
            with st.spinner("Processing clip and searching database..."):
                # Load audio (limit to first 15 seconds for fast query resolution)
                y, sr = fingerprinter.load_audio(target_clip, duration=15.0)
                if y is None:
                    st.error("Could not load selected audio clip.")
                else:
                    duration = len(y) / sr
                    
                    # Compute spectrogram & peaks
                    spectrogram = fingerprinter.compute_spectrogram(y, sr)
                    peaks = fingerprinter.get_peaks(spectrogram)
                    hashes = fingerprinter.generate_hashes(peaks, mode=db.mode)
                    
                    # Run search
                    matches, candidates = fingerprinter.match_query(hashes, db)
                    
                    if not candidates:
                        st.error("No matches found in the database.")
                    else:
                        top_match = candidates[0]
                        confidence = top_match['consensus_matches']
                        
                        # Decide threshold (e.g., minimum 5 matches for pairs)
                        threshold = 6 if db.mode == 'pairs' else 12
                        
                        if confidence >= threshold:
                            st.markdown(f"""
                            <div style="background-color: rgba(0, 210, 196, 0.1); border: 2px solid #00D2C4; padding: 24px; border-radius: 12px; margin-bottom: 24px; text-align: center;">
                                <div style="font-size: 14px; color: #A0AEC0; text-transform: uppercase; letter-spacing: 1px;">Identified Song</div>
                                <div style="font-size: 28px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">{top_match['song_name']}</div>
                                <div style="font-size: 14px; color: #A0AEC0; margin-top: 6px;">Consensus Matches: <strong>{confidence}</strong> / Total Matches: {top_match['total_matches']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background-color: rgba(229, 62, 62, 0.1); border: 2px solid #E53E3E; padding: 24px; border-radius: 12px; margin-bottom: 24px; text-align: center;">
                                <div style="font-size: 14px; color: #A0AEC0; text-transform: uppercase; letter-spacing: 1px;">Result</div>
                                <div style="font-size: 28px; font-weight: 800; color: #FFFFFF; margin-top: 4px;">No Decisive Match</div>
                                <div style="font-size: 14px; color: #A0AEC0; margin-top: 6px;">Top candidate '{top_match['song_name']}' only has <strong>{confidence}</strong> matches (threshold is {threshold})</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        # Show Candidate Scores
                        st.markdown("<div class='section-header'>Candidate Scores</div>", unsafe_allow_html=True)
                        df_candidates = pd.DataFrame(candidates)[['song_name', 'consensus_matches', 'total_matches', 'best_offset']].head(5)
                        df_candidates.columns = ["Song Title", "Consensus Matches (Spike)", "Total Matching Hashes", "Time Offset (Frames)"]
                        
                        # Plot candidate bar chart
                        fig_cand, ax_cand = plt.subplots(figsize=(8, 3), facecolor='#0E1117')
                        ax_cand.set_facecolor('#1A202C')
                        y_pos = np.arange(len(df_candidates))
                        ax_cand.barh(y_pos, df_candidates["Consensus Matches (Spike)"], color='#00D2C4', height=0.5)
                        ax_cand.set_yticks(y_pos)
                        ax_cand.set_yticklabels(df_candidates["Song Title"], color='#E2E8F0', fontsize=10)
                        ax_cand.set_xlabel("Consensus Matches (Spike Height)", color='#E2E8F0')
                        ax_cand.spines['top'].set_visible(False)
                        ax_cand.spines['right'].set_visible(False)
                        ax_cand.spines['left'].set_color('#2D3748')
                        ax_cand.spines['bottom'].set_color('#2D3748')
                        ax_cand.tick_params(colors='#E2E8F0')
                        ax_cand.invert_yaxis()  # top-down
                        st.pyplot(fig_cand)
                        plt.close(fig_cand)
                        
                        # Detailed steps
                        st.markdown("<div class='section-header'>Step 1: Feature Extraction</div>", unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Spectrogram of the clip** (Duration: {duration:.2f}s)")
                            fig_spec, ax_spec = plt.subplots(figsize=(6, 3.5), facecolor='#0E1117')
                            ax_spec.set_facecolor('#0E1117')
                            # Show spectrogram heatmap
                            img = ax_spec.imshow(spectrogram, origin='lower', aspect='auto', cmap='magma',
                                                 extent=[0, duration, 0, sr / 2])
                            ax_spec.set_xlabel("Time (s)", color='#FAFAFA')
                            ax_spec.set_ylabel("Frequency (Hz)", color='#FAFAFA')
                            ax_spec.tick_params(colors='#FAFAFA')
                            fig_spec.colorbar(img, ax=ax_spec, label='dB')
                            st.pyplot(fig_spec)
                            plt.close(fig_spec)
                            
                        with col2:
                            st.write(f"**Constellation of peaks** ({len(peaks)} local maxima)")
                            fig_peaks, ax_peaks = plt.subplots(figsize=(6, 3.5), facecolor='#0E1117')
                            ax_peaks.set_facecolor('#1A202C')
                            peaks_arr = np.array(peaks)
                            ax_peaks.scatter(peaks_arr[:, 0] * fingerprinter.DEFAULT_HOP / sr, 
                                             peaks_arr[:, 1] * sr / fingerprinter.DEFAULT_NFFT, 
                                             color='#00D2C4', s=12, edgecolors='none', alpha=0.8)
                            ax_peaks.set_xlim(0, duration)
                            ax_peaks.set_ylim(0, sr / 2)
                            ax_peaks.set_xlabel("Time (s)", color='#FAFAFA')
                            ax_peaks.set_ylabel("Frequency (Hz)", color='#FAFAFA')
                            ax_peaks.tick_params(colors='#FAFAFA')
                            st.pyplot(fig_peaks)
                            plt.close(fig_peaks)
                            
                        st.markdown("<div class='section-header'>Step 2: Database Search & Time Alignment</div>", unsafe_allow_html=True)
                        
                        # Plot offset histogram
                        st.write(f"**Offset alignment histogram** for candidate: **{top_match['song_name']}**")
                        fig_hist, ax_hist = plt.subplots(figsize=(10, 3.5), facecolor='#0E1117')
                        ax_hist.set_facecolor('#1A202C')
                        
                        # Retrieve offsets for this candidate
                        candidate_idx = top_match['song_idx']
                        candidate_offsets = matches[candidate_idx]
                        
                        # Time-scale bins to seconds
                        frame_to_sec = fingerprinter.DEFAULT_HOP / sr
                        sec_offsets = np.array(candidate_offsets) * frame_to_sec
                        
                        # Plot histogram
                        # We use small bins of frame size to see alignment clearly
                        ax_hist.hist(sec_offsets, bins=100, color='#00D2C4', edgecolor='#0E1117', alpha=0.8)
                        ax_hist.set_xlabel("Relative Time Offset (seconds)", color='#FAFAFA')
                        ax_hist.set_ylabel("Match Count", color='#FAFAFA')
                        ax_hist.set_title(f"Peak occurs at offset: {top_match['best_offset'] * frame_to_sec:.3f} s", color='#00D2C4', fontsize=12)
                        ax_hist.tick_params(colors='#FAFAFA')
                        st.pyplot(fig_hist)
                        plt.close(fig_hist)
                        
                        # Visual alignment overlay (where is the query clip in the full song)
                        if candidate_idx in db.song_peaks:
                            song_peaks = db.song_peaks[candidate_idx]
                            if len(song_peaks) > 0:
                                st.write("**Visual peak overlay inside the full song**")
                                fig_align, ax_align = plt.subplots(figsize=(12, 4), facecolor='#0E1117')
                                ax_align.set_facecolor('#1A202C')
                                
                                song_peaks_arr = np.array(song_peaks)
                                song_times_sec = song_peaks_arr[:, 0] * frame_to_sec
                                song_freqs_hz = song_peaks_arr[:, 1] * sr / fingerprinter.DEFAULT_NFFT
                                
                                # Plot full song peaks in grey
                                ax_align.scatter(song_times_sec, song_freqs_hz, color='#4A5568', s=3, alpha=0.5, label='Song peaks')
                                
                                # Highlight the matched window
                                match_start_sec = top_match['best_offset'] * frame_to_sec
                                match_end_sec = match_start_sec + duration
                                
                                ax_align.axvspan(match_start_sec, match_end_sec, color='#00D2C4', alpha=0.15, label='Matched window')
                                
                                # Highlight overlapping matching peaks
                                # Find peaks in the query that aligned with the song
                                best_offset = top_match['best_offset']
                                matched_song_peaks = []
                                
                                # Simple proximity matching to show query peaks overlay
                                query_peaks_shifted = [(t + best_offset, f) for t, f in peaks]
                                song_peaks_set = set(song_peaks)
                                
                                for pt, pf in query_peaks_shifted:
                                    if (pt, pf) in song_peaks_set:
                                        matched_song_peaks.append((pt * frame_to_sec, pf * sr / fingerprinter.DEFAULT_NFFT))
                                        
                                if matched_song_peaks:
                                    matched_arr = np.array(matched_song_peaks)
                                    ax_align.scatter(matched_arr[:, 0], matched_arr[:, 1], color='#00D2C4', s=15, edgecolors='#FFFFFF', linewidths=0.5, label='Matching hashes')
                                    
                                ax_align.set_xlim(0, max(song_times_sec) + 5)
                                ax_align.set_ylim(0, sr / 2)
                                ax_align.set_xlabel("Song Time (s)", color='#FAFAFA')
                                ax_align.set_ylabel("Frequency (Hz)", color='#FAFAFA')
                                ax_align.tick_params(colors='#FAFAFA')
                                ax_align.legend(loc='upper right', facecolor='#1A202C', edgecolor='#2D3748', labelcolor='#FAFAFA')
                                st.pyplot(fig_align)
                                plt.close(fig_align)

# ----------------- TAB 3: BATCH -----------------
with tab_batch:
    st.markdown("<div class='section-header'>Identify Many Clips at Once</div>", unsafe_allow_html=True)
    
    if db is None:
        st.warning("Please index or upload a fingerprint database in the LIBRARY tab before running batch queries.")
    else:
        st.write("Upload a set of query audio files. They will be identified against the currently loaded library, and you can download the standard `results.csv` file.")
        
        # Multiple file upload or zip upload
        batch_mode_type = st.radio("Batch upload method", ["Multiple Audio Files", "ZIP Archive of Audio Files"])
        
        uploaded_batch_files = []
        if batch_mode_type == "Multiple Audio Files":
            uploaded_batch_files = st.file_uploader("Upload audio clips", type=["wav", "mp3", "flac", "ogg", "m4a"], accept_multiple_files=True)
        else:
            zip_file = st.file_uploader("Upload ZIP archive", type=["zip"])
            if zip_file is not None:
                with zipfile.ZipFile(zip_file) as z:
                    for filename in z.namelist():
                        # Skip directories or non-audio files
                        if filename.startswith('__MACOSX') or not filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
                            continue
                        
                        # Extract file into bytes buffer
                        data = z.read(filename)
                        uploaded_batch_files.append({
                            'name': os.path.basename(filename),
                            'data': io.BytesIO(data)
                        })
                        
        if len(uploaded_batch_files) > 0:
            st.write(f"Ready to process **{len(uploaded_batch_files)}** clips.")
            
            if st.button("Run Batch Identification"):
                results = []
                progress_bar = st.progress(0)
                
                for idx, file_obj in enumerate(uploaded_batch_files):
                    # Handle both streamlit UploadedFile and our extracted zip buffer dict
                    if isinstance(file_obj, dict):
                        fname = file_obj['name']
                        fdata = file_obj['data']
                    else:
                        fname = file_obj.name
                        fdata = file_obj
                        
                    # Process clip (limit to first 15 seconds for fast batch query resolution)
                    y, sr = fingerprinter.load_audio(fdata, duration=15.0)
                    prediction = "none"
                    
                    if y is not None:
                        spectrogram = fingerprinter.compute_spectrogram(y, sr)
                        peaks = fingerprinter.get_peaks(spectrogram)
                        hashes = fingerprinter.generate_hashes(peaks, mode=db.mode)
                        _, candidates = fingerprinter.match_query(hashes, db)
                        
                        threshold = 6 if db.mode == 'pairs' else 12
                        if candidates and candidates[0]['consensus_matches'] >= threshold:
                            prediction = candidates[0]['song_name']
                            
                    results.append({
                        'filename': fname,
                        'prediction': prediction
                    })
                    
                    progress_bar.progress((idx + 1) / len(uploaded_batch_files))
                    
                # Create CSV
                df_results = pd.DataFrame(results)
                
                st.markdown("<div class='section-header'>Batch Results Preview</div>", unsafe_allow_html=True)
                st.dataframe(df_results, use_container_width=True)
                
                # CSV formatting: filename, prediction
                csv_buffer = io.StringIO()
                df_results.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label="Download results.csv",
                    data=csv_data,
                    file_name="results.csv",
                    mime="text/csv"
                )
