# The MIT License
#
# Copyright (c) <year> <copyright holders>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
package require Itcl

package provide gogame 1.0

namespace import itcl::*

class gogame {

    variable  ctm  ;# where in the game we are
    variable  bd
    variable  n
    variable  n1
    variable  nn
    variable  nnn
    variable  his  ;# a hash of board copies
    variable  mvs  ;# a hash  of moves
    variable  dir  ;# the 4 possible directions

    constructor {size} {

	set bd   ""
	set ctm  0
	set n    $size
	set n1   [expr $n + 1]
	set nn   [expr $size * $size]
	set nnn  [expr ($size + 1) * ($size + 2)]
	set dir  [list -1 1 $n1 [expr -1 * $n1]]

	for {set y 0} {$y < [expr $n + 2]} {incr y} {
	    for {set x 0} {$x < $n1} {incr x} {
		if {$y < 1 || $y > $n || $x == 0} {
		    lappend bd 3
		} else {
		    lappend bd 0
		}
	    }
	}

	set his($ctm) $bd
    }


    method  mvToIndex {mv} {

	set m  [string toupper $mv]

	if {[string range $m 0 1] == "PA"} {
	    return 0
	}

	if {[regexp {^[A-Z]\d+} $m]} {
	    set x [string range $m 0 0]
	    set y [expr $n1 - [string range $m 1 2]]
	    if {$y > $n} { return -4 }
	    scan $x %c x
	    if {$x == 73} { return -4 }  ;# illegal "I" character
	    if {$x > 72} {incr x -1}     ;# adjust for missing "I" character
	    set x [expr $x - 64]         ;# "A" is 1 now

	} else {
	    # puts "Sorry"
	    return -4
	}

	return [expr $y * $n1 + $x]   ;# index of point on board
    }



    # return a list of captured stones
    # --------------------------------
    method  capture_group {target} {

	set tbd $bd                    ;# copy of board for restoration if needed
	set lst [list $target]
	set est [lindex $bd $target]   ;# enemy (color of group to be captured)
	set ret [list $target]         ;# list of stones to return
	set flag($target) 1
	

	while {1} {

	    set nlst ""          ;# build a new list
	    foreach ix $lst {

		foreach d $dir {
		    set p [expr $d + $ix]
		    
		    if {[lindex $bd $p] == 0} {
			set bd $tbd
			return ""      ;# nothing captured nothing gained
		    }
		   

		    if {[lindex $bd $p] == $est} {   
			if {[info exists flag($p)] == 0} {
			    lappend nlst $p
			    lappend ret $p   ;# list of stones to be captured
			    set flag($p) 1
			}
		    }

		}
	    }


	    if {[llength $nlst] == 0} {
		foreach ix $ret {
		    set bd [lreplace $bd $ix $ix 0]
		}
		return $ret
	    } else {
		set lst $nlst
	    }
	}
    }
    

    method  colorToMove {} {
	return $ctm
    }



    # return a "board" with correct status
    # ------------------------------------
    method  score_board {dead_list} {

	set b $bd                    ;# work from a copy

	# kill the dead stones
	# --------------------------------
	foreach s $dead_list {
	    set imv [mvToIndex $s]
	    set b [lreplace $b $imv $imv 0]
	}

	for {set x 1} {$x < $n1} {incr x} {
	    for {set y 1} {$y < $n1} {incr y} {

		set i [expr ($y * $n1) + $x]

		if {[lindex $b $i] == 0} {   ;# empty square and hasn't been covered yet

		    set lst [list $i]
		    set cc 0                  ;# color of surrounding stones
		    set flag($i) 1
		    
		    while {1} {
			
			set nlst ""          ;# build a new list
			foreach ix $lst {
			    
			    foreach d $dir {
				set p [expr $d + $ix]
				
				if {[lindex $b $p] == 0 && [info exists flag($p)]==0} {
				    lappend nlst $p
				    set flag($p) 1
				} elseif {[lindex $b $p] == 1} {   
				    set cc [expr $cc | 1]
				} elseif {[lindex $b $p] == 2} {
				    set cc [expr $cc | 2]
				}
			    }
			}
			
			if {[llength $nlst] == 0} {
			    if {$cc == 1 || $cc == 2} {
				foreach ix [array names flag] {
				    set b [lreplace $b $ix $ix $cc]
				}
			    }
			    unset flag
			    break
			} else {
			    set lst $nlst
			}
		    }
		    
		}
		
	    }
	}

	return $b
    }
    




#  make -
#
#   Return: -4  if str_move formatted wrong
#   Return: -3  move to occupied square
#   Return: -2  Simple KO move
#   Return: -1  suicide
#   Return   0  non capture move
#   Return  >0  number of stones captured
#   --------------------------------------   

    method make {mov} { 

	set mv   [string toupper $mov]
	set fst [expr 2 - ($ctm & 1)]   ;# friendly stone color
	set est [expr $fst ^ 3]         ;# enemy stone color

	if {[string range $mv 0 1] == "PA"} {
	    set mvs($ctm) PASS
	    incr ctm
	    set his($ctm) $bd
	    return 0
	}

	if {[regexp {^[A-Z]\d+} $mv]} {
	    set x [string range $mv 0 0]
	    set y [expr $n1 - [string range $mv 1 2]]
	    if {$y > $n} { return -4 }
	    scan $x %c x
	    if {$x == 73} { return -4 }  ;# illegal "I" character
	    if {$x > 72} {incr x -1}     ;# adjust for missing "I" character
	    set x [expr $x - 64]         ;# "A" is 1 now

	} else {
	    # puts "Sorry"
	    return -4
	}

	set ix [expr $y * $n1 + $x]   ;# index of point on board

	if {[lindex $bd $ix] != 0} { return -3 }  ;# move to occupied square

	set bd [lreplace $bd $ix $ix $fst]

	# determine if a capture was made in one or more directions
	# ---------------------------------------------------------
	set clist ""
	foreach d $dir {
	    set p [expr $d + $ix]
	    if {[lindex $bd $p] == $est} {
		set clist [concat $clist [capture_group $p]]
	    }
	}

	# is the move suicidal?
	# ---------------------
	if {[llength $clist] == 0} {   ;# move was not a capture!
	    if {[llength [capture_group $ix]] > 0} {
		set bd $his($ctm)
		return -1
	    }
	}

	# test for KO
	# ------------
	for {set i 0} {$i < $ctm} {incr i} {
	    if {$his($i) eq $bd} {
		set bd $his($ctm)
		return -2    ;# KO move
	    }
	}
	

	# ok, the move was apparently valid!  accept it.
	# ----------------------------------------------
	set mvs($ctm) $mv
	incr ctm
	set his($ctm) $bd
	return [llength $clist]
    }


    method unmake {} {
	if {$ctm > 0} {
	    incr ctm -1
	    set bd $his($ctm)
	    return 1
	} else {
	    return 0
	}
    }

    method unmakeAll {} {
	set ctm 0
	set bd $his($ctm)
	return 0
    }


    method twopass {} {
	if {$ctm > 1} {
	    if {$mvs([expr $ctm - 1]) == "PASS" && $mvs([expr $ctm - 2]) == "PASS"} {
		return 1
	    } else {
		return 0
	    }
	} else {
	    return 0
	}
    }

    method list_moves {} {
	
	set  all ""
	
	for {set ix 0} {$ix < $ctm} {incr ix} {
	    lappend all $mvs($ix)
	}
	
	return $all
    }


    method displayAll {} {

	for {set y 0} {$y < [expr $n + 2]} {incr y} {
	    puts ""
	    for {set x 0} {$x < $n1} {incr x} {
		set ix [expr $y * $n1 + $x]
		puts -nonewline [format "%3d" [lindex $bd $ix]]
	    }
	}
	
	puts "\n"
    }


    method display {} {

	for {set y 1} {$y <= $n} {incr y} {
	    puts ""
	    for {set x 1} {$x <= $n} {incr x} {
		set ix [expr $y * $n1 + $x]
		puts -nonewline [format "%3d" [lindex $bd $ix]]
	    }
	}
	
	puts "\n"
    }


    # return a copy of the current board as a tcl list
    # ------------------------------------------------
    method getboard {} {
	set board ""
	for {set y 1} {$y <= $n} {incr y} {
	    for {set x 1} {$x <= $n} {incr x} {
		set ix [expr $y * $n1 + $x]
		lappend board [lindex $bd $ix]
	    }
	}
	return $board
    }


    # return a copy of the current board as a tcl list
    # ------------------------------------------------
    method getFinalBoard {dead} {
	set b [score_board $dead]
	set board ""
	for {set y 1} {$y <= $n} {incr y} {
	    for {set x 1} {$x <= $n} {incr x} {
		set ix [expr $y * $n1 + $x]
		lappend board [lindex $b $ix]
	    }
	}
	return $board
    }


}



