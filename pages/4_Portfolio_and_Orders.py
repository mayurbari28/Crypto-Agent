#Description: Portfolio positions, exposure, open orders, and actions.

import streamlit as st
from services.portfolio import PortfolioService
from services.execution import ExecutionService
from utils.charts import positions_table

st.title("Portfolio & Orders")

portfolio = PortfolioService.instance()
exec_service = ExecutionService.instance()

st.subheader("Open Positions")
pos_df = portfolio.get_open_positions_df()
st.dataframe(positions_table(pos_df), use_container_width=True)

st.subheader("Orders (Recent)")
orders = portfolio.get_orders_df(limit=50)
st.dataframe(orders, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    if st.button("Rebalance"):
        out = exec_service.rebalance()
        st.write(out)
with col2:
    if st.button("Close All Positions"):
        out = exec_service.close_all_positions()
        st.write(out)

st.subheader("Event Log")
for log in portfolio.get_recent_events(50):
    st.write(f"{log['ts']} [{log['level']}] {log['message']}")