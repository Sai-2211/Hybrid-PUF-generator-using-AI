create_clock -name system_clk -period 37.037 [get_ports {clk}]
# Review the intentional arbiter fabric clock and CDC in Gowin.
# No blanket timing waiver is supplied; controller/UART timing must pass.
