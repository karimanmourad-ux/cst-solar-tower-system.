import streamlit as st
import pandas as pd
import json

# ==============================================================================
# PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="CST Solar Tower Expert System",
    page_icon="☀️",
    layout="wide"
)

# ==============================================================================
# 1. DATABASE LAYER
# ==============================================================================
MATERIALS_DATABASE = {
    "receiver_pipes": {
        "ss316l": {"name": "Stainless Steel 316L", "max_temp_c": 550.0, "cost_per_kg_usd": 6.0, "yield_strength_mpa": 170.0, "corrosion_resistance_index": 7.0},
        "p91": {"name": "Chrome-Moly Alloy Steel P91", "max_temp_c": 600.0, "cost_per_kg_usd": 3.5, "yield_strength_mpa": 330.0, "corrosion_resistance_index": 5.0},
        "inconel_625": {"name": "Nickel Superalloy Inconel 625", "max_temp_c": 980.0, "cost_per_kg_usd": 35.0, "yield_strength_mpa": 415.0, "corrosion_resistance_index": 9.0},
        "inconel_740h": {"name": "Nickel Superalloy Inconel 740H", "max_temp_c": 850.0, "cost_per_kg_usd": 45.0, "yield_strength_mpa": 560.0, "corrosion_resistance_index": 9.0}
    },
    "selective_coatings": {
        "pyromark_2500": {"name": "Pyromark 2500 Paint", "solar_absorptivity": 0.96, "thermal_emissivity": 0.85, "max_temp_c": 650.0, "cost_per_m2_usd": 12.0},
        "comn_spinel": {"name": "Spinel Ceramic Nanocoating", "solar_absorptivity": 0.95, "thermal_emissivity": 0.18, "max_temp_c": 750.0, "cost_per_m2_usd": 25.0}
    },
    "tes_storage_media": {
        "solar_salt": {"name": "Binary Solar Salt", "t_melt_c": 238.0, "t_decomp_c": 600.0, "density_kg_m3": 1838.0, "cp_kj_kgk": 1.556, "thermal_conductivity_w_mk": 0.5185, "cost_per_kg_usd": 0.80},
        "hitec_xl": {"name": "Ternary Hitec XL", "t_melt_c": 133.0, "t_decomp_c": 500.0, "density_kg_m3": 1990.0, "cp_kj_kgk": 1.450, "thermal_conductivity_w_mk": 0.530, "cost_per_kg_usd": 1.10},
        "carbonate_eutectic": {"name": "Carbonate Eutectic Salt", "t_melt_c": 397.0, "t_decomp_c": 750.0, "density_kg_m3": 1980.0, "cp_kj_kgk": 1.800, "thermal_conductivity_w_mk": 0.750, "cost_per_kg_usd": 4.50}
    },
    "nanoparticles": {
        "gnp": {"name": "Graphene Nanoplatelets (GNP)", "density_kg_m3": 2300.0, "cp_kj_kgk": 0.710, "thermal_conductivity_w_mk": 3000.0, "cp_enhancement_factor_per_vol_pct": 0.050, "cost_per_kg_usd": 100.0},
        "alpha_alumina": {"name": "Alpha-Alumina (Al2O3)", "density_kg_m3": 3980.0, "cp_kj_kgk": 0.7955, "thermal_conductivity_w_mk": 30.0, "cp_enhancement_factor_per_vol_pct": 0.080, "cost_per_kg_usd": 25.0},
        "silica": {"name": "Silicon Dioxide (SiO2)", "density_kg_m3": 2200.0, "cp_kj_kgk": 0.740, "thermal_conductivity_w_mk": 1.4, "cp_enhancement_factor_per_vol_pct": 0.120, "cost_per_kg_usd": 15.0}
    }
}

# ==============================================================================
# 2. CORE ENGINES
# ==============================================================================
def synthesize_nanofluid(base_salt_key, nano_key, vol_conc, req_kwh):
    base = MATERIALS_DATABASE["tes_storage_media"][base_salt_key]
    nano = MATERIALS_DATABASE["nanoparticles"][nano_key]
    phi = vol_conc
    
    rho_nf = (1.0 - phi) * base["density_kg_m3"] + phi * nano["density_kg_m3"]
    cp_ideal = ((1.0 - phi) * (base["density_kg_m3"] * base["cp_kj_kgk"]) + phi * (nano["density_kg_m3"] * nano["cp_kj_kgk"])) / rho_nf
    cp_synth = cp_ideal * (1.0 + (phi * nano["cp_enhancement_factor_per_vol_pct"] * 100.0))
    
    k_b, k_np = base["thermal_conductivity_w_mk"], nano["thermal_conductivity_w_mk"]
    k_synth = k_b * ((k_np + 2*k_b - 2*phi*(k_b - k_np)) / (k_np + 2*k_b + phi*(k_b - k_np)))
    
    q_kj = req_kwh * 3600.0
    vol_base = (q_kj / (base["cp_kj_kgk"] * 110.0)) / base["density_kg_m3"]
    mass_nf = q_kj / (cp_synth * 110.0)
    vol_nf = mass_nf / rho_nf
    
    mass_nano = mass_nf * (phi * nano["density_kg_m3"] / rho_nf)
    cost_nf = ((mass_nf - mass_nano) * base["cost_per_kg_usd"]) + (mass_nano * nano["cost_per_kg_usd"])
    
    return {
        "base_name": base["name"], "nano_name": nano["name"], "vol_pct": phi*100,
        "cp_base": base["cp_kj_kgk"], "cp_synth": cp_synth, "k_synth": k_synth,
        "vol_base": vol_base, "vol_nf": vol_nf, "vol_saved_pct": ((vol_base - vol_nf)/vol_base)*100,
        "cost_base": (q_kj / (base["cp_kj_kgk"] * 110.0)) * base["cost_per_kg_usd"], "cost_nf": cost_nf
    }

def evaluate_plant_lcoh(pipe_key, coating_key, salt_key, nano_res, plant_mw=10.0, storage_hrs=8.0):
    pipe = MATERIALS_DATABASE["receiver_pipes"][pipe_key]
    coating = MATERIALS_DATABASE["selective_coatings"][coating_key]
    
    rad_loss_factor = coating["thermal_emissivity"] / 0.85
    thermal_eff = 0.88 * (1.0 - (0.05 * rad_loss_factor))
    
    annual_mwh = (25000.0 * 2200.0 * (coating["solar_absorptivity"] * 0.75) * thermal_eff) / 1000.0
    
    capex_hel = 25000.0 * 110.0
    capex_rec = 1200000.0 * (pipe["cost_per_kg_usd"] / 6.0)
    capex_tank = nano_res["vol_nf"] * 1200.0
    capex_total = capex_hel + capex_rec + capex_tank + nano_res["cost_nf"]
    
    crf = (0.07 * (1.07)**25) / (((1.07)**25) - 1)
    ann_cost = (capex_total * crf) + (0.02 * capex_total)
    lcoh = ann_cost / annual_mwh
    
    return {"capex": capex_total, "lcoh_mwh": lcoh, "lcoh_gj": lcoh/3.6, "eff": thermal_eff*100}

# ==============================================================================
# 3. STREAMLIT UI
# ==============================================================================
st.title("☀️ CST Solar Tower Multi-Material Science Decision System")
st.markdown("Expert decision-support framework for Solar Tower materials, multi-component innovation, and ANSYS/SAM software export.")

# Sidebar Settings
st.sidebar.header("⚙️ Plant Parameters")
target_temp = st.sidebar.slider("Operating Temperature (°C)", 400, 800, 550, 25)
plant_mw = st.sidebar.number_input("Thermal Capacity (MW_th)", 1.0, 100.0, 10.0)
storage_hrs = st.sidebar.number_input("Storage Duration (Hours)", 1.0, 16.0, 8.0)

st.sidebar.header("🔬 Material Selections")
pipe_sel = st.sidebar.selectbox("Receiver Pipe Alloy", list(MATERIALS_DATABASE["receiver_pipes"].keys()), format_func=lambda x: MATERIALS_DATABASE["receiver_pipes"][x]["name"])
coat_sel = st.sidebar.selectbox("Selective Coating", list(MATERIALS_DATABASE["selective_coatings"].keys()), format_func=lambda x: MATERIALS_DATABASE["selective_coatings"][x]["name"])
salt_sel = st.sidebar.selectbox("TES Base Salt", list(MATERIALS_DATABASE["tes_storage_media"].keys()), format_func=lambda x: MATERIALS_DATABASE["tes_storage_media"][x]["name"])
nano_sel = st.sidebar.selectbox("Nanoparticle Additive", list(MATERIALS_DATABASE["nanoparticles"].keys()), format_func=lambda x: MATERIALS_DATABASE["nanoparticles"][x]["name"])
nano_conc = st.sidebar.slider("Nanoparticle Volume (%)", 0.1, 3.0, 1.0, 0.1) / 100.0

# Calculations
req_kwh = plant_mw * 1000.0 * storage_hrs
nano_res = synthesize_nanofluid(salt_sel, nano_sel, nano_conc, req_kwh)
plant_res = evaluate_plant_lcoh(pipe_sel, coat_sel, salt_sel, nano_res, plant_mw, storage_hrs)

# Tabs Output
tab1, tab2, tab3 = st.tabs(["📊 Performance & LCOH", "🧪 Nanofluid Chemistry", "💾 Export (SAM / ANSYS / COMSOL)"])

with tab1:
    st.subheader("📌 Plant Performance Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Thermal Efficiency", f"{plant_res['eff']:.1f}%")
    c2.metric("Required Tank Volume", f"{nano_res['vol_nf']:,.1f} m³", delta=f"-{nano_res['vol_saved_pct']:.1f}% Saved")
    c3.metric("Total Plant CAPEX", f"${plant_res['capex']:,.0f}")
    c4.metric("LCOH", f"${plant_res['lcoh_mwh']:.2f} / MWh", f"${plant_res['lcoh_gj']:.2f} / GJ")

with tab2:
    st.subheader("🔬 Synthesized Nanofluid Thermophysical Properties")
    st.write(f"**Base Fluid:** {nano_res['base_name']} | **Additive:** {nano_res['vol_pct']:.1f}% Vol {nano_res['nano_name']}")
    col_a, col_b = st.columns(2)
    col_a.metric("Synthesized Specific Heat (Cp)", f"{nano_res['cp_synth']:.3f} kJ/kg·K", f"+{((nano_res['cp_synth']-nano_res['cp_base'])/nano_res['cp_base'])*100:.1f}%")
    col_b.metric("Synthesized Conductivity (k)", f"{nano_res['k_synth']:.3f} W/m·K")

with tab3:
    st.subheader("💾 Export Material Data for External Software")
    st.markdown("Download generated input files for NREL SAM and ANSYS/COMSOL simulation tools.")
    
    # Generate SAM JSON string
    sam_json = json.dumps({"media_name": nano_res["base_name"], "cp": nano_res["cp_synth"], "k": nano_res["k_synth"], "vol_m3": nano_res["vol_nf"]}, indent=4)
    st.download_button("📥 Download NREL SAM Input File (.json)", data=sam_json, file_name="sam_cst_config.json", mime="application/json")
    
    # Generate ANSYS CSV Data
    df_ansys = pd.DataFrame({
        "Property": ["Density", "Specific Heat", "Thermal Conductivity", "Tank Volume"],
        "Value": [1850.0, nano_res["cp_synth"]*1000.0, nano_res["k_synth"], nano_res["vol_nf"]],
        "Units": ["kg/m3", "J/kg·K", "W/m·K", "m3"]
    })
    csv_data = df_ansys.to_csv(index=False)
    st.download_button("📥 Download ANSYS / COMSOL FEA Table (.csv)", data=csv_data, file_name="ansys_comsol_properties.csv", mime="text/csv")