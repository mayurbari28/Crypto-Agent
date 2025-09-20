#Description: Secure API key onboarding and connectivity tests.

import streamlit as st

from utils.security import SecretsVault
from adapters.coindcx_spot import CoinDCXSpotAdapter
from adapters.coindcx_futures import CoinDCXFuturesAdapter

st.title("API & Keys")

vault = SecretsVault.instance()

with st.form("keys_form"):
    st.subheader("Spot API Keys")
    spot_key = st.text_input("COINDCX_API_KEY", type="password")
    spot_secret = st.text_input("COINDCX_API_SECRET", type="password")
    st.subheader("Futures API Keys")
    fut_key = st.text_input("COINDCX_FUT_API_KEY", type="password")
    fut_secret = st.text_input("COINDCX_FUT_API_SECRET", type="password")
    save = st.form_submit_button("Save Keys Securely")
    if save:
        if spot_key and spot_secret:
            vault.store("spot", spot_key, spot_secret)
        if fut_key and fut_secret:
            vault.store("futures", fut_key, fut_secret)
        st.success("Keys saved. They are encrypted at rest.")

st.subheader("Connectivity Test")
if st.button("Test Spot Connectivity"):
    adapter = CoinDCXSpotAdapter()
    ok, msg = adapter.test_connectivity()
    st.write("Result:", ok, msg)
if st.button("Test Futures Connectivity"):
    adapter = CoinDCXFuturesAdapter()
    ok, msg = adapter.test_connectivity()
    st.write("Result:", ok, msg)

st.info("Mode is configured via .env (MODE=live|paper|dryrun). In paper/dryrun, orders are simulated.")
