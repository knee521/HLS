set root [file normalize [file join [file dirname [info script]] ..]]
set mode "all"
if {[info exists ::env(EXP3_HLS_MODE)]} { set mode $::env(EXP3_HLS_MODE) }
set variant "baseline"
if {[info exists ::env(EXP3_HLS_VARIANT)]} { set variant $::env(EXP3_HLS_VARIANT) }
if {$variant ni {baseline serialized}} { error "Unknown HLS variant" }
set flags "-std=c++03"
if {$variant eq "serialized"} { append flags " -DEXP3_NO_PIPELINE" }
file mkdir [file join $root build]
cd [file join $root build]
# Vivado HLS 2018.3 expects a project name, not a drive-qualified path.
open_project hls_$variant
set_top nn_infer
add_files [file join $root hls nn_infer.cpp] -cflags $flags
add_files [file join $root hls nn_infer.h]
add_files [file join $root hls weights.h]
add_files -tb [file join $root hls tb_nn.cpp] -cflags "-std=c++03"
open_solution "solution1"
set_part {xc7a35tfgg484-2}
create_clock -period 20 -name default
set vectors [file join $root data vectors]
set evidence [file join $root evidence simulation]
file mkdir $evidence
if {$mode in {all csim}} {
    csim_design -clean -argv "$vectors test $evidence/csim_$variant.csv"
}
if {$mode in {all synth}} { csynth_design }
if {$mode in {all cosim}} {
    cosim_design -rtl verilog -tool xsim -trace_level all -argv "$vectors cosim $evidence/cosim_$variant.csv"
}
if {$mode in {all export}} { export_design -format ip_catalog }
if {$mode ni {all csim synth cosim export}} { error "Unknown HLS mode" }
puts "EXP3_HLS_PASS $mode $variant"
exit
