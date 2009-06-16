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
package provide app-gogo 1.0

package require Tk
package require gogame


array set gamelist {}

# handicap points for different board sizes
# set hcp(9)   [list 2 4 6]
# set hcp(11)  [list 3 5 7]
# set hcp(13)  [list 3 6 9]
# set hcp(15)  [list 3 7 11]
# set hcp(17)  [list 3 8 13]
# set hcp(19)  [list 3 9 15]


set lcol [list \#ffffff \#f0f0f0]
set ci 0

# set up image directory
# ----------------------
set  idir "$starkit::topdir/lib/app-gogo/images"

set  server www.greencheeks.homelinux.org
set  port   1415

# active_games are games that the user wants to watch on the screen
#
# killed_games are games that the user has exited - but the GUI still
# continues to track those games internally - so they remain on the
# active games list.   When gameover arrives, both entries are removed.
#
# If a game is killed and restarted before it has completed, it is 
# re-created and broought up to date by the data inside active_games and the 
# killed_games record is removed
# --------------------------------------------------------------------------

array set active_games {}
array set killed_games {}  

# -slant italic etc.
# -------------------------------------------------------
font create norm -family Helvetica -size 8
font create bold  -family Helvetica -size 8 -weight bold  
font create small -family Helvetica -size 8 -weight bold  



class game_board {

    variable  gme
    variable  n
    variable  gid
    variable  uptr    ;# user pointer into game
    variable  mvs     ;# a list of moves into game
    variable  num     ;# number of moves so far

    #common  bgcolor \#607060
    common  bgcolor \#809080

    common  lighter \#D0D8D0

    common  ssz  22   ;# based on graphics images
    common  half 11
    common  boff 33
    common  csz  
    common  bdimg  [image create photo -file "$idir/wood.gif"]
    common  wstone [image create photo -file "$idir/wstone.gif"]
    common  bstone [image create photo -file "$idir/bstone.gif"]
    common  bd_bg_color  \#ffffff
    common  fleg [list A B C D E F G H J K L M N O P Q R S T U V W X Y Z]
    common  rleg [list 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25]

    
    
    # note: only works for boardsize 9
    common hcp     [list 2 4 6]


    
    constructor {gameid size blackName whiteName} {
	
	set gid  $gameid
	set n    $size	
	set csz  [expr {($n + 2) * $ssz}]
	set uptr 0
	set num  0
	set gme "gme$gid"
	set mvs {}

	
	
	gogame $gme $n
	
	toplevel .$gid -width [expr ($n + 8) * $ssz] -height [expr 4 + ($n + 7) * $ssz] -bg $bgcolor
	
	canvas .$gid.bd  -bg $bd_bg_color -height $csz  -width $csz -bd 3 -relief groove
	
	bind .$gid <Destroy> [list killGame $gid]
	
	label .$gid.bwho  -bg \#404040 -fg \#ffffff -text "Black: $blackName"  -anchor w
	place  .$gid.bwho  -x [expr $half + 4] -y 12 -width $csz
	
	label .$gid.wwho  -bg \#f0f0f0 -fg \#000000 -text "White: $whiteName"  -anchor w
	place  .$gid.wwho  -x [expr $half + 4]  -y [expr  4 + $ssz + $half] -width $csz
	
	for {set a 0} {$a < 21} {incr a} {
	    for {set b 0} {$b < 21} {incr b} {
		.$gid.bd create image [expr $a * 96] [expr $b * 96] -anchor nw -image $bdimg 
	    }
	}
	
	# Draw the board on the canvas
	# ----------------------------
	for {set i 0} { $i < $n } { incr i } {
	    set  os [expr $boff + $ssz * $i]
	    set  ex [expr $half + $n * $ssz]
	    .$gid.bd create line $os  $boff  $os $ex
	    .$gid.bd create line $boff $os $ex $os
	    
	    # draw the file legend
	    # --------------------
	    set ch [lindex $fleg $i]
	    .$gid.bd create text $os [expr $ssz * 0.75]  -text $ch
	    .$gid.bd create text $os [expr $ssz * $n + ($ssz * 1.3)]  -text $ch
	    
	    # draw the rank legend
	    # --------------------
	    set ch [lindex $rleg [expr $n - $i - 1]]
	    .$gid.bd create text [expr $ssz * 0.95] [expr 1 + $os] -text $ch -anchor e
	    .$gid.bd create text [expr $ssz * $n + ($ssz * 1.1)] [expr 1 + $os] -text $ch -anchor w
	}
	
	# set handicapp points
	# --------------------
	if {$n >= 9 && $n <= 19} {
	    if {[expr $n & 1] == 1} {
		foreach xx $hcp {
		    foreach yy $hcp {
			.$gid.bd create oval [expr -2 + $boff + $ssz * $xx] [expr -2 + $boff + $ssz * $yy] [expr 2 + $boff + $ssz * $xx] [expr 2 + $boff + $ssz * $yy]
			.$gid.bd create oval [expr -1 + $boff + $ssz * $xx] [expr -1 + $boff + $ssz * $yy] [expr 1 + $boff + $ssz * $xx] [expr 1 + $boff + $ssz * $yy]
		    }
		}
	    }
	}
	
	# make 4 navigation buttons
	# -------------------------
	set  buttonsz 56
	set  buttonsp  6

	set y [expr 4 + $boff + $ssz * ($n + 4)]

	set sx [expr ($boff + $ssz * $n * 0.5) -  0.5 * (($buttonsz*4) + ($buttonsp*3)) ]
	
	for {set ix 0} {$ix < 4} {incr ix} {
	    set x [expr $sx + $ix * ($buttonsz + $buttonsp)]
	    set x [expr 4 + int($x)]
	    button .$gid.mvb$ix -highlightthickness 0  -relief raised -background $lighter -font small -command [list gb$gid navigate $ix]
	    place .$gid.mvb$ix -x $x -y $y -width $buttonsz
	}

	.$gid.mvb0 configure -text "<<"
	.$gid.mvb1 configure -text "<"
	.$gid.mvb2 configure -text ">"
	.$gid.mvb3 configure -text ">>"

	
	# set up the label for announcing the final results
	# -------------------------------------------------
	set x [expr 8 + $ssz + 6 * 40]
	label .$gid.res  -text {playing ...} -background white -font small
	place .$gid.res -x $x  -y [expr 4 + $ssz + $half] -width 90

	# place  .$gid.wwho  -x [expr $half + 4]  -y [expr  4 + $ssz + $half] -width $csz
	
	
	# play the board itself
	place  .$gid.bd  -x $half  -y [expr $ssz * 3]
    }
    
    method destructor {} {
	delete object $gme
    }


    
    
    # display the board
    # -----------------
    method  updateBoard {} {
	
	set  nn [expr $n * $n]
	set stones [$gme getboard]
	
	.$gid.bd delete stone
	
	for {set j 0} {$j < $nn} { incr j } {
	    
	    set c [lindex $stones $j]
	    if {$c == 1} {
		
		set yy [expr $j / $n]
		set xx [expr $j % $n]
		
		.$gid.bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $wstone -tags stone
	    }
	    
	    if {$c == 2} {
		
		set yy [expr $j / $n]
		set xx [expr $j % $n]
		
		.$gid.bd create image [expr $boff + $ssz * $xx] [expr $boff + $ssz * $yy] -image $bstone -tags stone
	    }
	}
    }


    method OldUpdateGameScore {} {
	set a [$gme list_moves]
	set count [llength $a]

	if { $count <= 5 } { 
	    set sv 0
	} else { 
	    set sv [expr $count - 5]
	}

	set bn 0
	while {$sv < $count} {
	    .$gid.mvb$bn configure -text [lindex $a $sv]
	    incr sv
	    incr bn
	}
    }


    method updateResults {res} {
	.$gid.res configure -text $res
    }


    # user pushed a navigation button
    # -------------------------------
    method navigate {ix} {

	if { $ix == 0 } {
	    set uptr 0
	    $gme unmakeAll
	    updateBoard
	    return 0
	}

	if { $ix == 1 } {
	    if { $uptr > 0 } {
		$gme unmake
		incr uptr -1
		updateBoard
	    }
	}


	if { $ix == 2 } {
	    if { $uptr < $num } {
		# for debugging
		# .$gid.res configure -text "mv: [lindex $mvs $uptr]"
		# puts "make [lindex $mvs $uptr]
		$gme make [lindex $mvs $uptr]
		incr uptr
		updateBoard
	    }
	}

	if { $ix == 3 } {
	    while { $uptr < $num } {
		$gme make [lindex $mvs $uptr]
		incr uptr
	    }
	    updateBoard
	}

    }


    method makeMove {mv} {

	lappend mvs $mv

	if { $uptr == $num } {
	    incr num
	    incr uptr
	    $gme make $mv
	    updateBoard
	} else {
	    incr num
	}
    }

}


proc  killGame {gid} {
    global killed_games
    global active_games

    # has this record been handled already?
    if { ! [info exists active_games($gid)] } {
	return
    }

    if { ! [info exists killed_games($gid)] } {
	# puts  "Game $gid is history!"
	set killed_games($gid) 1
	delete object gb$gid

	# is the game record is complete, remove this from active_games too
	# puts [lindex $active_games($gid)]
	if { [lindex [lindex $active_games($gid) end] 0] == "gameover" } {
	    unset active_games($gid)
	    unset killed_games($gid)
	}
    }
}


wm geometry . "600x400"
wm resizable . 0 0




# make a heading Canvas
# ---------------------
canvas .hc -bg \#e8e0d0 -height 30 -width 580 -relief flat -borderwidth 0


# make a scrollable canvas
# ------------------------
scrollbar .sy -orient v -command ".c yview"  -borderwidth 3
canvas .c -yscrollcommand ".sy set" -bg \#e8e0d0  -height 340 -width 580 -relief flat -borderwidth 0


place  .c  -x 0 -y 30
place .hc -x 0 -y 0

place .sy -x 582 -y 30 -height 340
.c configure -scrollregion {0 0 680 5000} 


# put a heading on canvas
# ------------------------

 .hc create rectangle 4 6 68 26 
 .hc create text  66  16 -anchor e -text Game  -font bold

 .hc create rectangle 74 6 274 26
 .hc create text  76  16 -anchor w -text "Black Player" -font bold

 .hc create rectangle 280 6 480 26
 .hc create text 282  16 -anchor w -text "White Player" -font bold 

 .hc create rectangle 486 6 576 26
 .hc create text 488  16 -anchor w -text "Results" -font bold 

# .c create rectangle 572 6 674 26
# .c create text 488  16 -anchor w -text "Results" -font bold 


proc timestring {tm} {

    set m [expr int($tm / 60)]
    set s [expr int($tm - ($m * 60.0))]

    return [format "%02d:%02d" $m $s]
}


proc doit {gid} {
    global active_games
    global killed_games
    if { [info exists active_games($gid) ] } {
	puts "You are already watching that game."
    } else {
	global sock
	puts $sock "observe $gid"
    }
}



proc get_message {sock} {

    global active_games
    global killed_games
    global gamelist
    global lcol
    global ci


    if {[catch {gets $sock data}] || [eof $sock]} {
	catch {close $sock}
    } else {

	# set d [split $data "\n"]
	foreach {nonsense} {loop_of_one} {

	    # puts $data
	    set msg [split $data]
	    set key [lindex $msg 0]
	    
	    if {$key == "match"} {
		
		# match 11 AnchorMan(1500) wimpy(1500) 1155239441
		
		set gid [lindex $msg 1]
		set bid [lindex $msg 2]
		set wid [lindex $msg 3]
		set stt [lindex $msg 4]
		set brt -
		set wrt -
		set res -


		if { ! [info exists gamelist($gid) ] } {
		    .c move glist 0 17
		    .c create rectangle 2 3 596 20 -tags "glist Xg$gid" -fill [lindex $lcol $ci] -outline [lindex $lcol $ci]
		    set ci [expr {$ci ^ 1}]
		    .c create text  66  12 -anchor e -text $gid -tags "glist Ag$gid" -font bold -fill blue
		    .c create text  76  12 -anchor w -text $bid -tags "glist Bg$gid" -font bold -fill blue
		    .c create text 282  12 -anchor w -text $wid -tags "glist Cg$gid" -font bold -fill blue
		    .c create text 488  12 -anchor w -text "- playing" -tags "glist Dg$gid" -font bold -fill blue
		    .c create rectangle 2 3 596 20 -tags "glist Zg$gid" -fill "" -outline ""
		    .c bind Zg$gid <1> [list doit $gid]
		    
		}
		
		set gamelist($gid) [list $gid $bid $wid $stt $brt $wrt $res]
		continue
	    }
	    
	    if {$key == "gameover"} {
		
		# gameover 11 AnchorMan(1500) 85.072 wimpy(1499) 95.676 B+17.5
		
		set gid [lindex $msg 1]
		set bid [lindex $msg 2]
		set brt [lindex $msg 3]
		set wid [lindex $msg 4]
		set wrt [lindex $msg 5]
		set res [lindex $msg 6]
		#set stt [lindex $gamelist($gid) 2]
		set stt -
		set cde [string index $res 0]

		if {[info exists gamelist($gid)]} {
		    .c itemconfigure Ag$gid -fill \#303030
		    if {$cde == "B"} { set col \#000000 } else { set col \#808080 }
		    .c itemconfigure Bg$gid -fill $col  -text $bid
		    if {$cde == "W"} { set col \#000000 } else { set col \#808080 }
		    .c itemconfigure Cg$gid -fill $col -text $wid
		    .c itemconfigure Dg$gid -fill \#303030 -text $res
		    # .c itemconfigure Eg$gid -fill \#303030 -text "[timestring $brt] [timestring $wrt]"
		} else {
		    .c move glist 0 17
		    .c create rectangle 2 3 596 20 -tags "glist Xg$gid" -fill [lindex $lcol $ci] -outline [lindex $lcol $ci]
		    set ci [expr {$ci ^ 1}]
		    .c create text  66  12 -anchor e -text $gid -tags "glist Ag$gid" -font bold -fill \#303030
		    if {$cde == "B"} { set col \#000000 } else { set col \#808080 }
		    .c create text  76  12 -anchor w -text $bid -tags "glist Bg$gid" -font bold -fill $col
		    if {$cde == "W"} { set col \#000000 } else { set col \#808080 }
		    .c create text 282  12 -anchor w -text $wid -tags "glist Cg$gid" -font bold -fill $col
		    .c create text 488  12 -anchor w -text $res -tags "glist Dg$gid" -font bold -fill \#303030
		    .c create rectangle 2 3 596 20 -tags "glist Zg$gid" -fill "" -outline ""
		    .c bind Zg$gid <1> [list doit $gid]
		}

		set gamelist($gid) [list $gid $bid $wid $stt $brt $wrt $res]
		continue
	    }

	    if {$key == "gid"} {
		set gid [lindex $msg 1]
		lappend active_games($gid) [lrange $msg 2 end]
		set cc [llength $active_games($gid)]
		if {$cc == 6} {
		    set bp [lindex [lindex $active_games($gid) 2] 0]
		    set wp [lindex [lindex $active_games($gid) 3] 0]

		    if {![info exists killed_games($gid)]} {
			game_board gb$gid $gid 9 $bp $wp
		    }
		} elseif {$cc > 6} {
		    if {[lindex $msg 2] != "gameover"} {
			if {![info exists killed_games($gid)]} {
			    gb$gid makeMove [lindex $msg 2]
			}

		    } elseif {[lindex $msg 2] == "gameover"} {

			if { ![info exists killed_games($gid) ] } {
			    gb$gid updateResults [lindex $msg 3]
			}

		    } else {
			# not being watched?
			# ------------------
			if {[info exists killed_games($gid)]} {
			    unset killed_games($gid)
			    unset active_games($gid)
			}
		    }
		}
		continue
	    }
	}
    }
}



set err [catch {set sock [socket $server $port]} msg]
if {$err} {
    puts stderr "could not execute"
    exit 1
}

fconfigure $sock -buffering line -blocking 0


# Set up handler to "respond" when a message comes in
# ---------------------------------------------------
fileevent $sock readable [list get_message $sock]



