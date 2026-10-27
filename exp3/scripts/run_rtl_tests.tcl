# Vivado 2018.3 batch driver; test name is supplied using -tclargs.
set root [file normalize [file join [file dirname [info script]] ..]]
set test [expr {$argc > 0 ? [lindex $argv 0] : "tb_uart"}]
if {![regexp {^tb_[a-z0-9_]+$} $test]} { error "Invalid test identifier" }
set work [file join $root build simulation $test]
file mkdir $work
cd $work
set bin [file dirname [info nameofexecutable]]
# info nameofexecutable points into bin/unwrapped/win64.o on some installations.
set bin "D:/HLS/software/Xilinx/Vivado/2018.3/bin"
set sources [glob [file join $root rtl *.v]]
if {$test in {tb_system tb_watchdog}} {
    set hls [file join $root build hls_baseline solution1 syn verilog]
    set sources [concat $sources [glob [file join $hls *.v]]]
    foreach file [glob -nocomplain [file join $hls *.dat]] { file copy -force $file $work }
    foreach file [glob [file join $root data vectors *.hex]] { file copy -force $file $work }
}
set tb [file join $root sim ${test}.sv]
set output [exec [file join $bin xvlog.bat] --sv {*}$sources $tb 2>@1]
puts $output
set output [exec [file join $bin xelab.bat] $test -s ${test}_snapshot -debug typical 2>@1]
puts $output
set output [exec [file join $bin xsim.bat] ${test}_snapshot -runall 2>@1]
puts $output
if {[string first "TEST_PASS $test" $output] < 0 || [string first "Fatal:" $output] >= 0} {
    error "Simulation did not meet its assertions"
}
exit
