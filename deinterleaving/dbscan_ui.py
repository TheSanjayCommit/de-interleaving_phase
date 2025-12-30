import streamlit as st
import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN, KMeans
import matplotlib.pyplot as plt

# Try importing HDBSCAN from sklearn (v1.3+) or hdbscan package
try:
    from sklearn.cluster import HDBSCAN
    HAS_HDBSCAN = True
    HDBSCAN_LIB = "sklearn"
except ImportError:
    try:
        import hdbscan
        HAS_HDBSCAN = True
        HDBSCAN_LIB = "hdbscan"
    except ImportError:
        HAS_HDBSCAN = False
        HDBSCAN_LIB = None

def dbscan_ui():

    # Load persistent state
    state = st.session_state.dbscan_state

    st.header("De-Interleaving Phase")

    st.info(
        "Select a Data Source (Live Simulation or CSV) and a Clustering Algorithm "
        "to separate interleaved PDWs into emitters."
    )

    # -----------------------------
    # 1. DATA SOURCE SELECTION
    # -----------------------------
    
    # Check default index based on last activity
    last_mode = st.session_state.get("last_active_mode", "Auto")
    default_idx = 0 if last_mode == "Auto" else 1

    data_source = st.radio(
        "Data Source",
        ["Auto Mode (Live)", "Manual Mode (Live)"],
        index=default_idx,
        horizontal=True
    )

    df_input = None
    known_emitters = None
    
    # Logic to load data based on source
    if data_source == "Auto Mode (Live)":
        if st.button("Load/Refresh from Auto Mode"):
            buf = st.session_state.get("pdw_buffer", [])
            if not buf:
                st.warning("Auto Mode buffer is empty. Run simulation first.")
            else:
                df = pd.DataFrame(buf)
                state["df"] = df
                state["filename"] = "Auto Mode Live Data"
                state["results"] = None
                state["summary"] = None
                # Clear tuned params so it auto-tunes again for new data
                if "tuned_params" in state: del state["tuned_params"]
                if "tuned_params_dbscan" in state: del state["tuned_params_dbscan"]
                
        df_input = state.get("df")
        # Try to get config
        if "auto_config" in st.session_state:
             known_emitters = st.session_state.auto_config.get("num_emitters")

    elif data_source == "Manual Mode (Live)":
        if st.button("Load/Refresh from Manual Mode"):
            buf = st.session_state.get("manual_pdw_buffer", [])
            if not buf:
                st.warning("Manual Mode buffer is empty. Run simulation first.")
            else:
                df = pd.DataFrame(buf)
                state["df"] = df
                state["filename"] = "Manual Mode Live Data"
                state["results"] = None
                state["summary"] = None
                # Clear tuned params
                if "tuned_params" in state: del state["tuned_params"]
                if "tuned_params_dbscan" in state: del state["tuned_params_dbscan"]

        df_input = state.get("df")
        if "manual_config" in st.session_state:
             known_emitters = st.session_state.manual_config.get("num_emitters")

    # If no data loaded yet
    if df_input is None:
        return

    # -----------------------------
    # RAW INPUT PREVIEW
    # -----------------------------
    st.subheader(f"Input Data: {state.get('filename', 'Unknown')}")
    st.caption(f"Total PDWs: {len(df_input)}")
    if known_emitters:
        st.success(f"Simulation Ground Truth: **{known_emitters} Emitters**")
    
    st.dataframe(df_input.head(10))
    st.divider()

    # -----------------------------
    # -----------------------------
    # 2. FEATURE SELECTION
    # -----------------------------
    st.subheader("Feature Selection")
    
    saved_feats = state.get("features", ["freq_MHz", "pri_us"])

    c1, c2, c3, c4 = st.columns(4)
    use_freq = c1.checkbox("Freq", value="freq_MHz" in saved_feats)
    use_pri = c2.checkbox("PRI", value="pri_us" in saved_feats)
    use_pw = c3.checkbox("PW", value="pw_us" in saved_feats)
    use_doa = c4.checkbox("DOA", value="doa_deg" in saved_feats)

    features = []
    if use_freq: features.append("freq_MHz")
    if use_pri: features.append("pri_us")
    if use_pw and "pw_us" in df_input.columns: features.append("pw_us")
    if use_doa and "doa_deg" in df_input.columns: features.append("doa_deg")
    
    state["features"] = features # Persist

    if len(features) < 1:
        st.error("Select at least 1 feature.")
        return

    st.divider()

    # -----------------------------
    # 3. ALGORITHM SELECTION
    # -----------------------------
    col_algo, col_params = st.columns([1, 2])

    with col_algo:
        algo_options = ["K-Means", "DBSCAN"]
        if HAS_HDBSCAN:
            algo_options.insert(1, "HDBSCAN")
        
        algorithm = st.selectbox("Clustering Algorithm", algo_options)

    with col_params:
        params = {}
        if algorithm == "K-Means":
            st.markdown("**K-Means Parameters**")
            # If we know the emitters, default to that, but allow override
            default_k = known_emitters if known_emitters else 3
            k_val = st.number_input("Number of Clusters (k)", 2, 50, int(default_k))
            params["n_clusters"] = k_val
            
            if known_emitters and k_val == known_emitters:
                st.info(f"✅ Matching known emitter count ({known_emitters})")
            elif known_emitters:
                st.warning(f"⚠️ Mismatch with known emitter count ({known_emitters})")

        elif algorithm == "HDBSCAN":
            st.markdown("**HDBSCAN Parameters**")
            
            # AUTOMATIC TUNING (No Button)
            # If we know target emitters and haven't tuned yet for this data:
            if known_emitters and "tuned_params" not in st.session_state.dbscan_state:
                
                with st.spinner(f"Automatically tuning HDBSCAN for {known_emitters} emitters..."):
                    best_score = float('inf')
                    best_mcs = 5
                    best_ms = 5
                    
                    # Search space
                    search_range = range(2, 40, 1) 
                    
                    for mcs in search_range:
                        ms = mcs 
                        
                        # Prepare data
                        X = df_input[features].values
                        X_scaled = StandardScaler().fit_transform(X)
                        
                        # Run fast fit
                        if HDBSCAN_LIB == "sklearn":
                            c = HDBSCAN(min_cluster_size=mcs, min_samples=ms)
                            l = c.fit_predict(X_scaled)
                        elif HDBSCAN_LIB == "hdbscan":
                            c = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=ms)
                            l = c.fit_predict(X_scaled)
                        else:
                            l = []
                            
                        # Count clusters
                        if len(l) > 0:
                            n_clusters = len(set(l)) - (1 if -1 in l else 0)
                        else:
                            n_clusters = 0
                            
                        err = abs(n_clusters - known_emitters)
                        
                        if err < best_score:
                            best_score = err
                            best_mcs = mcs
                            best_ms = ms
                        
                        if err == 0:
                            break
                    
                    # Save results
                    st.session_state.dbscan_state["tuned_params"] = {
                        "min_cluster_size": best_mcs, 
                        "min_samples": best_ms
                    }
                
                st.success(f"Auto-Tuned: Size={best_mcs} (Diff: {best_score})")

            # Use tuned params (or defaults if no tuning happened)
            tuned = st.session_state.dbscan_state.get("tuned_params", {})
            
            min_cluster_size = st.slider(
                "Min Cluster Size", 2, 50, 
                tuned.get("min_cluster_size", 5)
            )
            min_samples = st.slider(
                "Min Samples", 1, 50, 
                tuned.get("min_samples", 5)
            )
            params["min_cluster_size"] = min_cluster_size
            params["min_samples"] = min_samples
            st.caption("Density-based: Automatically finds number of clusters.")

        elif algorithm == "DBSCAN":
            st.markdown("**DBSCAN Parameters**")
            
            # AUTOMATIC TUNING
            if known_emitters and "tuned_params_dbscan" not in st.session_state.dbscan_state:
                 with st.spinner(f"Automatically tuning DBSCAN for {known_emitters} emitters..."):
                    best_score = float('inf')
                    best_eps = 0.5
                    best_ms = 5
                    
                    # Search space for EPS
                    # 0.1 to 2.0 usually covers scaled data (StandardScaler makes mean=0, std=1)
                    # We'll scan finely.
                    eps_range = np.arange(0.1, 3.0, 0.1)
                    
                    for eps in eps_range:
                        ms = 5 # Fix min_samples or tune it too? kept simple for now
                        
                        # Prepare data
                        X = df_input[features].values
                        X_scaled = StandardScaler().fit_transform(X)
                        
                        db = DBSCAN(eps=eps, min_samples=ms)
                        l = db.fit_predict(X_scaled)
                        
                        # Count clusters
                        if len(l) > 0:
                            n_clusters = len(set(l)) - (1 if -1 in l else 0)
                        else:
                            n_clusters = 0
                        
                        err = abs(n_clusters - known_emitters)
                        
                        if err < best_score:
                            best_score = err
                            best_eps = eps
                            best_ms = ms
                            
                        if err == 0:
                            break
                    
                    st.session_state.dbscan_state["tuned_params_dbscan"] = {
                        "eps": float(best_eps),
                        "min_samples": best_ms
                    }
                 st.success(f"Auto-Tuned: Eps={best_eps:.2f} (Diff: {best_score})")

            # Use tuned
            tuned = st.session_state.dbscan_state.get("tuned_params_dbscan", {})
            
            eps = st.slider("Epsilon (eps)", 0.1, 5.0, tuned.get("eps", 0.7), 0.1)
            min_samples = st.slider("Min Samples", 2, 20, tuned.get("min_samples", 5))
            params["eps"] = eps
            params["min_samples"] = min_samples

    # -----------------------------
    # RUN DE-INTERLEAVING
    # -----------------------------
    if st.button(f"Run {algorithm}"):
        
        # Scaling
        X = df_input[features].values
        X_scaled = StandardScaler().fit_transform(X)
        
        labels = []
        
        if algorithm == "K-Means":
            kmeans = KMeans(n_clusters=params["n_clusters"], random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            
        elif algorithm == "HDBSCAN":
            if HDBSCAN_LIB == "sklearn":
                clusterer = HDBSCAN(
                    min_cluster_size=params["min_cluster_size"],
                    min_samples=params["min_samples"]
                )
                labels = clusterer.fit_predict(X_scaled)
            elif HDBSCAN_LIB == "hdbscan":
                clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=params["min_cluster_size"],
                    min_samples=params["min_samples"]
                )
                labels = clusterer.fit_predict(X_scaled)
                
        elif algorithm == "DBSCAN":
            db = DBSCAN(eps=params["eps"], min_samples=params["min_samples"])
            labels = db.fit_predict(X_scaled)

        # Process Labels
        # Force Noise (-1) to 0 or similar? Usually we keep it as -1 or 0.
        # Let's map unique labels to 1..N. Noise (-1) goes to 0 ("Unidentified").
        unique_labels = sorted(set(labels))
        # Logic: if -1 exists, map it to 0. Others map to 1, 2, 3...
        label_map = {}
        counter = 1
        for l in unique_labels:
            if l == -1:
                label_map[l] = 0 # Noise
            else:
                label_map[l] = counter
                counter += 1
                
        state["results"] = [label_map[l] for l in labels]
        state["algo_used"] = algorithm
        state["summary"] = {
            "total": len(df_input),
            "num_clusters": len(set(label_map.values())) - (1 if 0 in label_map.values() else 0),
            "noise_points": list(labels).count(-1),
            "known_emitters": known_emitters
        }
        
        st.success("De-Interleaving Completed")

    # -----------------------------
    # DISPLAY RESULTS
    # -----------------------------
    if state.get("results") is not None:
        
        df_display = df_input.copy()
        df_display["Emitter_ID"] = state["results"]
        # Label 0 as "Noise" for clarity? Or just keep ID 0.
        
        summ = state.get("summary", {})
        
        # Determine success color based on count match
        detected = summ.get('num_clusters', 0)
        expected = summ.get('known_emitters')
        
        match_msg = ""
        if expected:
            if detected == expected:
                match_msg = "✅ **MATCHES** Simulation Count"
            else:
                match_msg = f"⚠️ **MISMATCH** (Expected {expected})"

        st.markdown(
            f"""
            ### Results ({state.get('algo_used')})
            - **Detected Emitters:** {detected} {match_msg}
            - **Noise Points:** {summ.get('noise_points', 0)}
            """
        )

        st.subheader("Emitter-Wise Pulse Consistency")
        summary_df = (
            df_display.groupby("Emitter_ID")
              .agg(
                  Count=("Emitter_ID", "count"),
                  Freq_Mean=("freq_MHz", "mean"),
                  Freq_Std=("freq_MHz", "std"),
                  PRI_Mean=("pri_us", "mean"),
                  PRI_Std=("pri_us", "std")
              )
              .reset_index()
              .round(2)
        )
        st.dataframe(summary_df)

        st.subheader("Cluster Visualization")
        fig, ax = plt.subplots()
        
        # Plot Noise first (black/grey)
        noise = df_display[df_display["Emitter_ID"] == 0]
        if not noise.empty:
            ax.scatter(noise["toa_us"], noise["freq_MHz"], c="lightgrey", s=10, label="Noise", alpha=0.5)
            
        # Plot Clusters
        clusters = df_display[df_display["Emitter_ID"] > 0]
        if not clusters.empty:
            scatter = ax.scatter(
                clusters["toa_us"], 
                clusters["freq_MHz"], 
                c=clusters["Emitter_ID"], 
                cmap="tab10", 
                s=15
            )
            # Legend? usually too many points, but colour bar might help
            # plt.colorbar(scatter, ax=ax)
            
        ax.set_xlabel("TOA (µs)")
        ax.set_ylabel("Frequency (MHz)")
        ax.set_title(f"De-Interleaving Results ({state.get('algo_used')})")
        st.pyplot(fig)
        
        # Save to User Directory
        out_dir = st.session_state.get("user_output_dir", "outputs")
        df_display.to_csv(f"{out_dir}/deinterleaved_pdws.csv", index=False)
        
        st.toast("✅ De-Interleaving Analysis Saved!", icon="💾")
        st.info(f"Result saved to {out_dir}/deinterleaved_pdws.csv")
