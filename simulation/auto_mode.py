import streamlit as st
import numpy as np
import pandas as pd
import os

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

np.random.seed(42)

# =================================================
# SESSION STATE FOR CONTINUOUS TIME
# =================================================
if "global_time_us" not in st.session_state:
    st.session_state.global_time_us = 0.0

if "pdw_buffer" not in st.session_state:
    st.session_state.pdw_buffer = []

if "auto_running" not in st.session_state:
    st.session_state.auto_running = False

# =================================================
# AUTO MODE UI
# =================================================
def auto_mode_ui():

    st.header("Auto Mode – PDW Simulation (Continuous Time)")
    st.info("PDWs are generated in 2-second continuous time blocks")

    # Load config or set defaults
    cfg = st.session_state.auto_config

    num_emitters = st.number_input(
        "Number of Emitters",
        min_value=1,
        max_value=100,
        value=cfg.get("num_emitters", 10),
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

    # -----------------------------
    # EMITTER DISTRIBUTION
    # -----------------------------
    st.subheader("Emitter Type Distribution (%)")

    fixed_pct = st.number_input("Fixed Emitters (%)", 0, 100, cfg.get("fixed_pct", 60))
    cfg["fixed_pct"] = fixed_pct

    agile_pct = st.number_input("Frequency Agile Emitters (%)", 0, 100, cfg.get("agile_pct", 25))
    cfg["agile_pct"] = agile_pct

    stagger_pct = st.number_input("Staggered PRI Emitters (%)", 0, 100, cfg.get("stagger_pct", 15))
    cfg["stagger_pct"] = stagger_pct

    if fixed_pct + agile_pct + stagger_pct != 100:
        st.error("Emitter percentages must sum to 100")
        return

    # -----------------------------
    # PARAMETER LIMITS
    # -----------------------------
    st.subheader("Parameter Ranges")

    f_min = st.number_input("Frequency Min (MHz)", 500.0, 40000.0, cfg.get("f_min", 8000.0))
    cfg["f_min"] = f_min
    f_max = st.number_input("Frequency Max (MHz)", 500.0, 40000.0, cfg.get("f_max", 12000.0))
    cfg["f_max"] = f_max

    pri_min = st.number_input("PRI Min (µs)", 2.0, 20000.0, cfg.get("pri_min", 2000.0))
    cfg["pri_min"] = pri_min
    pri_max = st.number_input("PRI Max (µs)", 2.0, 20000.0, cfg.get("pri_max", 6000.0))
    cfg["pri_max"] = pri_max

    pw_min = st.number_input("Pulse Width Min (µs)", 0.01, 1000.0, cfg.get("pw_min", 1.0))
    cfg["pw_min"] = pw_min
    pw_max = st.number_input("Pulse Width Max (µs)", 0.01, 1000.0, cfg.get("pw_max", 50.0))
    cfg["pw_max"] = pw_max

    amp_min = st.number_input("Amplitude Min (dB)", -200.0, 10.0, cfg.get("amp_min", -80.0))
    cfg["amp_min"] = amp_min
    amp_max = st.number_input("Amplitude Max (dB)", -200.0, 10.0, cfg.get("amp_max", -30.0))
    cfg["amp_max"] = amp_max

    doa_min = st.number_input("DOA Min (deg)", 0.0, 360.0, cfg.get("doa_min", 0.0))
    cfg["doa_min"] = doa_min
    doa_max = st.number_input("DOA Max (deg)", 0.0, 360.0, cfg.get("doa_max", 360.0))
    cfg["doa_max"] = doa_max

    # =================================================
    # SIMULATION CONTROL (NEW)
    # =================================================
    st.subheader("Simulation Control")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶ Start / Generate"):
            st.session_state.auto_running = True

    with col2:
        if st.button("⏸ Pause"):
            st.session_state.auto_running = False

    with col3:
        if st.button("⏹ Reset"):
            st.session_state.auto_running = False
            st.session_state.global_time_us = 0.0
            st.session_state.pdw_buffer = []
            st.success("Auto mode reset")

    # =================================================
    # GENERATE NEXT 2s PDWs (ONLY WHEN STARTED)
    # =================================================
    if st.session_state.auto_running:

        df_new = generate_pdws_2s(
            num_emitters,
            pulses_per_emitter,
            fixed_pct,
            agile_pct,
            stagger_pct,
            f_min, f_max,
            pri_min, pri_max,
            pw_min, pw_max,
            amp_min, amp_max,
            doa_min, doa_max
        )

        # Use User Isolation (Default to 'outputs' if not set)
        out_dir = st.session_state.get("user_output_dir", "outputs")
        
        # Save to buffer
        st.session_state.pdw_buffer.extend(df_new.to_dict("records"))
        
        # Save to CSV
        df_all = pd.DataFrame(st.session_state.pdw_buffer)
        df_all = df_all.sort_values("toa_us").reset_index(drop=True)
        df_all = df_all.round(2)
        
        df_all.to_csv(f"{out_dir}/pdw_interleaved.csv", index=False)

        st.session_state.auto_running = False  # IMPORTANT: step-wise control
        st.session_state.last_active_mode = "Auto" # Track for De-Interleaving

        st.toast(f"✅ Generated 2s PDW Data! (Total: {len(df_all)})", icon="📡")
        st.success("Generated next 2 seconds of PDWs")
        st.write("Total PDWs so far:", len(df_all))
        st.dataframe(df_all.tail(20))


# =================================================
# PDW GENERATION FOR 2-SECOND WINDOW
# =================================================
def generate_pdws_2s(num_emitters, pulses_per_emitter,
                     fixed_pct, agile_pct, stagger_pct,
                     f_min, f_max, pri_min, pri_max,
                     pw_min, pw_max,
                     amp_min, amp_max,
                     doa_min, doa_max):

    rows = []

    window_start = st.session_state.global_time_us
    window_end = window_start + 2e6  # 2 seconds in µs
    st.session_state.global_time_us = window_end

    n_fixed = int(num_emitters * fixed_pct / 100)
    n_agile = int(num_emitters * agile_pct / 100)
    n_stagger = num_emitters - n_fixed - n_agile

    emitter_types = (
        ["fixed"] * n_fixed +
        ["agile"] * n_agile +
        ["stagger"] * n_stagger
    )
    np.random.shuffle(emitter_types)

    for etype in emitter_types:

        freq = np.random.uniform(f_min, f_max)
        pri = np.random.uniform(pri_min, pri_max)
        pw = np.random.uniform(pw_min, pw_max)
        amp = np.random.uniform(amp_min, amp_max)
        doa = np.random.uniform(doa_min, doa_max)

        freqs = (
            np.random.uniform(f_min, f_max, np.random.randint(2, 6))
            if etype == "agile" else [freq]
        )

        pri_set = (
            np.random.uniform(pri_min, pri_max, np.random.randint(2, 4))
            if etype == "stagger" else [pri]
        )

        toa = np.random.uniform(window_start, window_end)

        for k in range(pulses_per_emitter):
            pri_k = pri_set[k % len(pri_set)]

            rows.append({
                "freq_MHz": freqs[k % len(freqs)] + np.random.normal(0, 0.5),
                "pri_us": pri_k,
                "pw_us": pw,
                "doa_deg": doa + np.random.normal(0, 1),
                "amp_dB": amp + np.random.normal(0, 1),
                "toa_us": toa
            })

            toa += pri_k
            if toa > window_end:
                break

    return pd.DataFrame(rows)
