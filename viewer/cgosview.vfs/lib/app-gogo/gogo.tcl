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


set lcol [list \#ffffff \#f0f0f0]
set ci 0

# set up image directory
# ----------------------
set  idir "$starkit::topdir/lib/app-gogo/images"

set  server cgos.boardspace.net
set  port   6867

if {$argc > 0} {
    set server [lindex $argv 0]
    if {$argc > 1} {
	set port [lindex $argv 1]
    }
}



# this probably doesn't matter, it sets itself
# --------------------------------------------
set boardsize 9



# Make older tcl versions compatible with 8.5 by
# defining the lassign proc if it doesn't exist
# ------------------------------------------------------
if {[info procs lassign] eq ""} {
    proc lassign {values args} {
	uplevel 1 [list foreach $args [linsert $values end {}] break]
	lrange $values [llength $args] end
    }
}




# active_games are games that the user asked to observe
#
# if status of active_games is "y", game is being observed
# if status of active_games is "n", game is being tracked, but not observed.
# if record doesn't exist, it was never requested
# --------------------------------------------------------------------------

array set active_games {}

# layout of active_games
# ----------------------
#
#  gid status mv time mv time ...
#
#  status = "y"  -> being observed
#  status = "n"  -> not being observed
#




# -slant italic etc.
# -------------------------------------------------------
font create norm -family Helvetica -size 10 -weight bold
font create bold  -family Helvetica -size 9 -weight bold  
font create small -family Helvetica -size 9 -weight bold  


proc platform {} {
    global tcl_platform
    set plat [lindex $tcl_platform(os) 0]
    set mach $tcl_platform(machine)
    switch -glob -- $mach {
	sun4* { set mach sparc }
	intel -
	i*86* { set mach x86 }
	"Power Macintosh" { set mach ppc }
    }
    switch -- $plat {
	AIX   { set mach ppc }
	HP-UX { set mach hppa }
    }
    return "$plat-$mach"
}


set vers 0.32
set version "cgosview $vers [platform] by Don Dailey"

class game_board {

    variable  gme
    variable  n
    variable  gid
    variable  uptr    ;# user pointer into game
    variable  mvs     ;# a list of moves into game
    variable  num     ;# number of moves so far
    variable  hcp     ;# handicap points

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

    
    constructor {gameid size whiteName blackName} {
	
	global   vers
	set gid  $gameid
	set n    $size	
	set csz  [expr {($n + 2) * $ssz}]
	set uptr 0
	set num  0
	set gme "gme$gid"
	set mvs {}
	set handi(7)   [list 2 4]
	set handi(8)   [list 2 5]
	set handi(9)   [list 2 4 6]
	set handi(10)  [list 2 7]
	set handi(11)  [list 2 5 8]
	set handi(12)  [list 2 9]
	set handi(13)  [list 3 6 9]
	set handi(14)  [list 3 10]
	set handi(15)  [list 3 7 11]
	set handi(16)  [list 3 12]
	set handi(17)  [list 3 8 13]
	set handi(18)  [list 3 14]
	set handi(19)  [list 3 9 15]
	
	if { [info exists handi($size)] } {
	    set hcp  $handi($size)	
	} else {
	    set hcp {}
	}

	gogame $gme $n
	
	toplevel .$gid -width [expr ($n + 10) * $ssz] -height [expr 4 + ($n + 7) * $ssz] -bg $bgcolor
	
	canvas .$gid.bd  -bg $bd_bg_color -height $csz  -width $csz -bd 3 -relief groove
	
	bind .$gid <Destroy> [list killGame $gid]
	
	label .$gid.bwho  -bg \#404040 -fg \#ffffff -font norm -text "Black: $blackName"  -anchor w
	label .$gid.wwho  -bg \#f0f0f0 -fg \#000000 -font norm -text "White: $whiteName"  -anchor w

	place  .$gid.wwho  -x [expr $half + 4] -y 12 -width $csz
	place  .$gid.bwho  -x [expr $half + 4]  -y [expr  4 + $ssz + $half] -width $csz

	
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
	if {$n >= 7 && $n <= 19} {
	    foreach xx $hcp {
		foreach yy $hcp {
		    .$gid.bd create oval [expr -2 + $boff + $ssz * $xx] [expr -2 + $boff + $ssz * $yy] [expr 2 + $boff + $ssz * $xx] [expr 2 + $boff + $ssz * $yy]
		    .$gid.bd create oval [expr -1 + $boff + $ssz * $xx] [expr -1 + $boff + $ssz * $yy] [expr 1 + $boff + $ssz * $xx] [expr 1 + $boff + $ssz * $yy]
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
	set x [expr $boff + ($ssz * ($n + 2))] 
	label .$gid.res  -text {playing ...} -background white -font small
	place .$gid.res -x $x  -y [expr 4 + $ssz + $half] -width 90

	# place the version number of the display board
	# ---------------------------------------------
	set x [expr $boff + ($ssz * ($n + 2)) - 6]
	label .$gid.vers  -text "CGOS Viewer $vers" -background $bgcolor -fg white  -font small
	place .$gid.vers -x $x  -y 8 -width 120


	# set up the labels for displaying the game score
	# -----------------------------------------------

	label .$gid.gscbh -text "BLACK" -font small -anchor w
	place .$gid.gscbh -x [expr $boff + ($ssz * ($n + 2))] -y [expr $ssz * 4] -width 65 -anchor w

	label .$gid.gscwh -text "WHITE" -font small -anchor w 
	place .$gid.gscwh -x [expr $boff + 70 + ($ssz * ($n + 2))] -y [expr $ssz * 4] -width 65 -anchor w

	set mn 0
	for { set i 0 } { $i < $n } { incr i } {
	    set x [expr $boff + 2 + ($ssz * ($n + 2))]
	    label .$gid.gsc$mn -text "" -font small -background $bgcolor -foreground white -anchor w -width 65
	    place .$gid.gsc$mn -x $x -y [expr 4 + $ssz * ($i + 5)] -width 65 -anchor w

	    incr mn

	    set x [expr $boff + 70 + ($ssz * ($n + 2)) ]
	    label .$gid.gsc$mn -text "" -font small -background $bgcolor -foreground white -anchor w 
	    place .$gid.gsc$mn -x $x -y [expr 4 + $ssz * ($i + 5)] -width 65 -anchor w

	    incr mn
	}


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


    method updateGameScore {} {

	set count [llength $mvs]
	
	set n2 [expr $n * 2]

	if { $uptr != $count } {
	    set sv [expr ($uptr - $n) & (~1)]
	} else {
	    set sv [expr ($uptr - $n2 + 1) & (~1)]
	}

	if { $sv < 0 } {
	    set sv 0
	}


	for { set i 0 } { $i < $n2 } { incr i } {

	    set mn [expr $i + $sv]

	    if { $mn < $count } {
		set mstr "[expr $mn + 1]  [lindex $mvs $mn]"
	    } else {
		set mstr ""
	    }

	    .$gid.gsc$i configure -text $mstr
	    
	    if { $uptr == $mn + 1 } {
		.$gid.gsc$i configure -bg white -fg black

		# put a dot on the stone 
		# ----------------------
		set mv [lindex $mvs $mn]
		set ix [$gme mvToIndex $mv]
		set xmv [expr $boff + (($ix % ($n + 1)) - 1) * $ssz]
		set ymv [expr $boff + (($ix / ($n + 1)) - 1) * $ssz]

		if { $ix != 0 } {
		    if { $i & 1 } {
			.$gid.bd create oval [expr $xmv - 3] [expr $ymv - 3] [expr $xmv + 3] [expr $ymv + 3] -tags stone -fill black
		    } else {
			.$gid.bd create oval [expr $xmv - 3] [expr $ymv - 3] [expr $xmv + 3] [expr $ymv + 3] -tags stone -fill \#d0d0d0
		    }
		}
	    } else {
		.$gid.gsc$i configure -bg $bgcolor  -fg white
	    }
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
	    updateGameScore
	    return 0
	}

	if { $ix == 1 } {
	    if { $uptr > 0 } {
		$gme unmake
		incr uptr -1
		updateBoard
		updateGameScore
	    }
	}


	if { $ix == 2 } {
	    if { $uptr < $num } {
		$gme make [lindex $mvs $uptr]
		incr uptr
		updateBoard
		updateGameScore
	    }
	}

	if { $ix == 3 } {
	    while { $uptr < $num } {
		$gme make [lindex $mvs $uptr]
		incr uptr
	    }
	    updateBoard
	    updateGameScore
	}

    }


    method makeMove {mv} {

	lappend mvs $mv

	if { $uptr == $num } {
	    incr num
	    incr uptr
	    $gme make $mv
	    updateBoard
	    updateGameScore
	} else {
	    incr num
	    updateGameScore
	}
    }

}


proc  killGame {gid} {
    global active_games

    set lst [lassign $active_games($gid) xxx status]

    # see if widget already destroyed
    # -------------------------------
    if { $status == "n" } {
	return
    }

    lset  active_games($gid) 1 "n"

    delete object gb$gid
    
    # if the game record is complete, remove this from active_games too
    # -----------------------------------------------------------------
    set le [lindex $lst end]
    
    if { [string index $le 1] == "+" } {
	unset active_games($gid)
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
 .hc create text  76  16 -anchor w -text "White Player" -font bold

 .hc create rectangle 280 6 480 26
 .hc create text 282  16 -anchor w -text "Black Player" -font bold 

 .hc create rectangle 486 6 576 26
 .hc create text 488  16 -anchor w -text "Results" -font bold 

# .c create rectangle 572 6 674 26
# .c create text 488  16 -anchor w -text "Results" -font bold 


proc timestring {tm} {

    set m [expr int($tm / 60)]
    set s [expr int($tm - ($m * 60.0))]

    return [format "%02d:%02d" $m $s]
}


proc initiate_game {gid} {
    global  active_games
    global  boardsize
    global  gamelist

    # puts "INITIATE_GAME!"


    # handle the case where the active record exists
    # ----------------------------------------------
    if { [info exists active_games($gid)] } {

	set lst [lassign $active_games($gid) xxx status]

	if { $status == "y" } {
	    # puts "You are already watching that game."
	    return
	}

	lassign $gamelist($gid) x0 dte tme bs komi white black wrt brt

	game_board gb$gid $gid $boardsize $white $black

	lset active_games($gid) 1 "y" 

	foreach {mv tme} $lst {
	    if { [string index $mv 1] != "+" } {
		gb$gid makeMove $mv
	    } else {
		gb$gid updateResults $mv
	    }
	}

	return
    }  

    set active_games($gid) [list $gid y]

    global sock
    puts $sock "observe $gid"
}



proc get_message {sock} {

    global boardsize
    global active_games
    global gamelist
    global lcol
    global ci
    global version

    if {[catch {gets $sock data}] || [eof $sock]} {
	catch {close $sock}
	exit
    } 


    set msg [split $data]
    set key [lindex $msg 0]
    
    switch $key {
	"protocol"  {
	    puts $sock "v1 $version"
	}
	
	
	"match" {
	    #  puts "\"match\""
	    
	    lassign $data cmd gid dte tme boardsize komi wid bid res
	    
	    if { ! [info exists gamelist($gid) ] } {
		.c move glist 0 17
		.c create rectangle 2 3 596 20 -tags "glist Xg$gid" -fill [lindex $lcol $ci] -outline [lindex $lcol $ci]
		set ci [expr {$ci ^ 1}]
		.c create text  66  12 -anchor e -text $gid -tags "glist Ag$gid" -font bold -fill blue
		.c create text  76  12 -anchor w -text $wid -tags "glist Cg$gid" -font bold -fill blue
		.c create text 282  12 -anchor w -text $bid -tags "glist Bg$gid" -font bold -fill blue
		.c create text 488  12 -anchor w -text "- playing" -tags "glist Dg$gid" -font bold -fill blue
		.c create rectangle 2 3 596 20 -tags "glist Zg$gid" -fill "" -outline ""
		.c bind Zg$gid <1> [list initiate_game $gid]

		# game is complete ?
		# ------------------
		if { $res != "-" } {
		    set cde [string index $res 0]
		    .c itemconfigure Ag$gid -fill \#303030
		    if {$cde == "B"} { set col \#000000 } else { set col \#808080 }
		    .c itemconfigure Bg$gid -fill $col  -text $bid
		    if {$cde == "W"} { set col \#000000 } else { set col \#808080 }
		    .c itemconfigure Cg$gid -fill $col -text $wid
		    .c itemconfigure Dg$gid -fill \#303030 -text $res
		}
	    }
	    set gamelist($gid) [list $gid $dte $tme $boardsize $komi $wid $bid 0 0  $res]
	}
	
	
	"gameover" {
	    
	    # puts "hey gameover"

	    lassign $data cmd gid res wtime btime

	    lset gamelist($gid) 7 $wtime
	    lset gamelist($gid) 8 $btime
	    lset gamelist($gid) 9 $res
	    
	    lassign $gamelist($gid) x0 dte tme bs komi wid bid wrt brt
	    
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
		# puts "this should not happen here!"
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
		.c bind Zg$gid <1> [list initiate_game $gid]
	    }
	}
	
	"update" {
	    
	    lassign $data cmd gid mv trem

	    if { $mv != "resign" } {

		lappend active_games($gid) $mv $trem
		set mvs [lassign $active_games($gid) xxx status]
		if { $status == "y" } {
		    if { [string index $mv 1] != "+" } {
			gb$gid makeMove $mv
		    } else {
			gb$gid updateResults $mv
		    }
		}
	    }
	}


	"setup" {

	    set lst [lassign $data cmd gid dte tme bsz komi white black level]
	    set boardsize $bsz

	    game_board gb$gid $gid $boardsize $white $black

	    foreach {mv tme} $lst {
		lappend active_games($gid) $mv $tme
		if { [string index $mv 1] != "+" } {
		    gb$gid makeMove $mv
		} else {
		    gb$gid updateResults $mv
		}
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



