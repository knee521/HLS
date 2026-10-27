# USER-OPERATED ONLY. This script changes the FPGA's volatile configuration.
if {$argc != 1} { error "Usage: vivado -mode batch -source scripts/program_device.tcl -tclargs PATH_TO_BIT" }
set bit [file normalize [lindex $argv 0]]
if {![file isfile $bit] || [file extension $bit] ne ".bit"} { error "A valid bitstream path is required" }
open_hw
connect_hw_server
set targets [get_hw_targets]
if {[llength $targets] != 1} { error "Expected one JTAG target; choose the correct target manually in Hardware Manager" }
current_hw_target [lindex $targets 0]
open_hw_target
set devices [get_hw_devices]
if {[llength $devices] != 1} { error "Expected one FPGA; inspect the JTAG chain manually" }
set device [lindex $devices 0]
if {![string match "xc7a35t*" [get_property NAME $device]]} { error "Connected device is not XC7A35T" }
set_property PROGRAM.FILE $bit $device
program_hw_devices $device
refresh_hw_device $device
close_hw_target
disconnect_hw_server
close_hw
exit
