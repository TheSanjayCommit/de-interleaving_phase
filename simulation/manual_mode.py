import streamlit as st
import numpy as np
import pandas as pd
import os

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =================================================
# SESSION STATE
# =================================================
# =================================================
# MANUAL MODE UI
# =================================================
def manual_mode_ui():

    # =================================================
    # SESSION STATE INITIALIZATION (Must be inside function)
    # =================================================
    if "manual_global_time_us" not in st.session_state:
        st.session_state.manual_global_time_us = 0.0

    if "manual_pdw_buffer" not in st.session_state:
        st.session_state.manual_pdw_buffer = []

    if "manual_running" not in st.session_state:
        st.session_state.manual_running = False

    st.header("Manual Mode – PDW Simulation (Continuous Time)")
    st.info("PDWs are generated every 2 seconds using manually configured emitter parameters")

    
    # Load config
    cfg = st.session_state.manual_config
    saved_emitters = cfg.get("emitters", [])

    num_emitters = st.number_input(
        "Number of Emitters",
        min_value=1,
        max_value=20,
        value=cfg.get("num_emitters", 3),
        step=1
    )
    cfg["num_emitters"] = num_emitters

    pulses_per_emitter = st.number_input(
        "Pulses per Emitter (per 2s window)",
        min_value=1,
        max_value=1000,
        value=cfg.get("pulses_per_emitter", 20),
        step=1
    )
    cfg["pulses_per_emitter"] = pulses_per_emitter

    emitters = []

    st.subheader("Emitter Configuration")

    for i in range(num_emitters):
        st.markdown(f"### Emitter {i+1}")

        # specific saved state for this emitter index
        e_saved = saved_emitters[i] if i < len(saved_emitters) else {}

        freq_type = st.selectbox(
            "Frequency Type",
            ["Fixed", "Agile"],
            index=0 if e_saved.get("freq_type", "Fixed") == "Fixed" else 1,
            key=f"freq_type_{i}"
        )

        freqs = []
        if freq_type == "Agile":
            num_modes = st.number_input(
                "Number of Frequency Modes",
                min_value=2,
                max_value=10,
                value=e_saved.get("num_modes", 3),
                step=1,
                key=f"num_modes_{i}"
            )

            saved_freqs = e_saved.get("freqs", [])
            for m in range(num_modes):
                val = saved_freqs[m] if m < len(saved_freqs) else (9000.0 + m * 50)
                freqs.append(
                    st.number_input(
                        f"Mode {m+1} Frequency (MHz)",
                        500.0, 40000.0,
                        float(val),
                        key=f"freq_{i}_{m}"
                    )
                )
        else:
            saved_freqs = e_saved.get("freqs", [9000.0])
            val = saved_freqs[0] if len(saved_freqs) > 0 else 9000.0
            num_modes = 1 # Not used but good to track
            freqs = [
                st.number_input(
                    "Frequency (MHz)",
                    500.0, 40000.0,
                    float(val),
                    key=f"freq_{i}"
                )
            ]

        pri_type = st.selectbox(
            "PRI Type",
            ["Fixed", "Staggered"],
            index=0 if e_saved.get("pri_type", "Fixed") == "Fixed" else 1,
            key=f"pri_type_{i}"
        )

        pri_set = []
        if pri_type == "Staggered":
            num_pri = st.number_input(
                "Number of PRI Values",
                min_value=2,
                max_value=5,
                value=e_saved.get("num_pri", 2),
                key=f"num_pri_{i}"
            )

            saved_pris = e_saved.get("pri_set", [])
            for p in range(num_pri):
                val = saved_pris[p] if p < len(saved_pris) else (2000.0 + p * 500)
                pri_set.append(
                    st.number_input(
                        f"PRI {p+1} (µs)",
                        2.0, 20000.0,
                        float(val),
                        key=f"pri_{i}_{p}"
                    )
                )
        else:
            saved_pris = e_saved.get("pri_set", [2000.0])
            val = saved_pris[0] if len(saved_pris) > 0 else 2000.0
            num_pri = 1
            pri_set = [
                st.number_input(
                    "PRI (µs)",
                    2.0, 20000.0,
                    float(val),
                    key=f"pri_{i}"
                )
            ]

        pw = st.number_input(
            "Pulse Width (µs)",
            0.01, 1000.0,
            float(e_saved.get("pw", 10.0)),
            key=f"pw_{i}"
        )

        amp = st.number_input(
            "Amplitude (dB)",
            -200.0, 10.0,
            float(e_saved.get("amp", -60.0)),
            key=f"amp_{i}"
        )

        doa = st.number_input(
            "DOA (deg)",
            0.0, 360.0,
            float(e_saved.get("doa", 90.0)),
            key=f"doa_{i}"
        )

        # Store complete state for this emitter
        emitters.append({
            "freq_type": freq_type,
            "num_modes": num_modes if freq_type == "Agile" else 1,
            "freqs": freqs,
            "pri_type": pri_type,
            "num_pri": num_pri if pri_type == "Staggered" else 1,
            "pri_set": pri_set,
            "pw": pw,
            "amp": amp,
            "doa": doa
        })

    # Save all emitters back to config
    cfg["emitters"] = emitters

    st.divider()

    # =================================================
    # SIMULATION CONTROL (NEW)
    # =================================================
    st.subheader("Simulation Control")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶ Start / Generate"):
            st.session_state.manual_running = True

    with col2:
        if st.button("⏸ Pause"):
            st.session_state.manual_running = False

    with col3:
        if st.button("⏹ Reset"):
            st.session_state.manual_running = False
            st.session_state.manual_global_time_us = 0.0
            st.session_state.manual_pdw_buffer = []
            st.success("Manual mode reset")

    # =================================================
    # GENERATE NEXT 2s PDWs (ONLY WHEN STARTED)
    # =================================================
    if st.session_state.manual_running:

        df_new = generate_manual_pdws_2s(
            pulses_per_emitter,
            emitters
        )

        # Use User Isolation
        out_dir = st.session_state.get("user_output_dir", "outputs")

        st.session_state.manual_pdw_buffer.extend(df_new.to_dict("records"))

        df_all = pd.DataFrame(st.session_state.manual_pdw_buffer)
        df_all = df_all.sort_values("toa_us").reset_index(drop=True)
        # ✅ Round PDW values to 2 decimal places
        df_all = df_all.round(2)

        df_all.to_csv(f"{out_dir}/manual_interleaved.csv", index=False)

        st.session_state.manual_running = False  # step-wise control
        st.session_state.last_active_mode = "Manual" # Track for De-Interleaving

        st.toast(f"✅ Generated 2s Manual Data! (Total: {len(df_all)})", icon="🎛️")
        st.success("Generated next 2 seconds of PDWs (Manual Mode)")
        st.write("Total PDWs so far:", len(df_all))
        st.dataframe(df_all.tail(20))


# =================================================
# PDW GENERATION (2-SECOND WINDOW)
# =================================================
def generate_manual_pdws_2s(pulses_per_emitter, emitters):

    rows = []

    window_start = st.session_state.manual_global_time_us
    window_end = window_start + 2e6  # 2 seconds (µs)

    st.session_state.manual_global_time_us = window_end

    for e in emitters:

        toa = np.random.uniform(window_start, window_end)

        for k in range(pulses_per_emitter):

            freq = e["freqs"][k % len(e["freqs"])]
            pri = e["pri_set"][k % len(e["pri_set"])]

            rows.append({
                "freq_MHz": freq,
                "pri_us": pri,
                "pw_us": e["pw"],
                "doa_deg": e["doa"],
                "amp_dB": e["amp"] + np.random.normal(0, 1),
                "toa_us": toa
            })

            toa += pri
            if toa > window_end:
                break

    return pd.DataFrame(rows)
