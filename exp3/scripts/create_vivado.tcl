# Batch implementation only: this script never connects to or programs hardware.
set root [file normalize [file join [file dirname [info script]] ..]]
set configuration [expr {$argc > 0 ? [lindex $argv 0] : "baseline"}]
switch -- $configuration {
    baseline { set top exp3_top; set baud 115200 }
    medium { set top exp3_top; set baud 230400 }
    fast { set top exp3_top; set baud 460800 }
    bringup { set top bringup_top; set baud 115200 }
    default { error "Configuration must be baseline, medium, fast or bringup" }
}
set rightmost [expr {$argc > 1 ? [lindex $argv 1] : 0}]
if {![string is integer -strict $rightmost] || $rightmost < 0 || $rightmost > 5} {
    error "Rightmost digit index must be 0..5"
}
set work [file join $root build vivado_$configuration]
set evidence [file join $root evidence implementation $configuration]
file mkdir $work
file mkdir $evidence
cd $work
set_param general.maxThreads 4
create_project -force exp3_$configuration $work -part xc7a35tfgg484-2
add_files [glob [file join $root rtl *.v]]
if {$top eq "exp3_top"} {
    set hls [file join $root build hls_baseline solution1 syn verilog]
    add_files [glob [file join $hls *.v]]
    foreach data [glob -nocomplain [file join $hls *.dat]] {
        add_files $data
        file copy -force $data $work
    }
}
add_files -fileset constrs_1 [file join $root constraints exp3.xdc]
set_property top $top [current_fileset]
synth_design -top $top -part xc7a35tfgg484-2 -generic [list BAUD=$baud RIGHTMOST_INDEX=$rightmost]
# Only the asynchronous serial input to the first synchronizer stage is exempt.
set rx_first [get_cells -hierarchical -regexp {.*(receiver|rx)/synchronizer_reg\[0\]}]
if {[llength $rx_first] != 1} { error "Cannot identify exactly one UART synchronizer entry" }
set_false_path -from [get_ports uart_rxd] -to [get_pins -of_objects $rx_first -filter {REF_PIN_NAME == D}]
set reset_cells [get_cells -hierarchical -regexp {.*rst/sync_ff_reg\[[01]\]}]
if {[llength $reset_cells] != 2} { error "Cannot identify reset synchronizer stages" }
set_false_path -from [get_ports sys_rst_n] -to [get_pins -of_objects $reset_cells -filter {REF_PIN_NAME == PRE}]
# 5 ns is a conservative output budget, not a board-measured external clock relation.
set_output_delay -clock sys_clk -max 5 [get_ports {uart_txd led[*] seg_led[*] seg_sel[*]}]
set_output_delay -clock sys_clk -min 0 [get_ports {uart_txd led[*] seg_led[*] seg_sel[*]}]
write_checkpoint -force [file join $work post_synth.dcp]
opt_design
place_design
phys_opt_design
route_design
report_utilization -file [file join $evidence utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $evidence timing_summary.rpt]
report_drc -file [file join $evidence drc.rpt]
report_cdc -details -file [file join $evidence cdc.rpt]
check_timing -verbose -file [file join $evidence check_timing.rpt]
set worst [get_timing_paths -max_paths 1 -nworst 1]
if {[llength $worst] != 1 || [get_property SLACK $worst] < 0} { error "Setup timing failed" }
set hold [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
if {[llength $hold] != 1 || [get_property SLACK $hold] < 0} { error "Hold timing failed" }
set dsp [llength [get_cells -hierarchical -filter {REF_NAME == DSP48E1}]]
if {$dsp > 60} { error "DSP budget exceeded: $dsp" }
if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error}]] > 0} { error "DRC errors remain" }
write_checkpoint -force [file join $work post_route.dcp]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
write_bitstream -force [file join $work exp3.bit]
set output [open [file join $evidence build_summary.json] w]
puts $output "{\"configuration\":\"$configuration\",\"top\":\"$top\",\"baud\":$baud,\"rightmost_index\":$rightmost,\"wns_ns\":[get_property SLACK $worst],\"hold_slack_ns\":[get_property SLACK $hold],\"dsp\":$dsp,\"hardware_tested\":false}"
close $output
puts "EXP3_BUILD_PASS $configuration"
exit

